import asyncio
from datetime import datetime
from typing import Dict, List
from sqlalchemy.orm import Session
from services.logger import console
from routers.frontal import job_queue
from models.crop_model import DBCropJob
from drivers.database import engine, Base, SessionLocal

from services.metrics import (
    job_total_counter,
    job_completed_counter,
    job_failed_counter,
    job_processing_duration_seconds,
)

try:
    from exlib.pyc.image_processor import process_image_data_intensive

    console.log(
        "[bold green]Successfully imported Cythonized image_processor from exlib.pyc.[/bold green]"
    )
except ImportError:
    from exlib.py.image_processor import process_image_data_intensive

    console.log(
        "[bold yellow]Cythonized image_processor not found. Using pure Python version from exlib.py.[/bold yellow]"
    )


def points_to_svg_path(points_list: List[Dict[str, float]]):

    if not points_list:
        return ""

    path_commands = []

    path_commands.append(f"M {points_list[0]['x']} {points_list[0]['y']}")

    for point in points_list[1:]:
        path_commands.append(f"L {point['x']} {point['y']}")

    path_commands.append("Z")
    return " ".join(path_commands)


# --- Background Job Processing Worker ---
async def process_jobs_worker(
    job_queue: asyncio.Queue,
    db_session_factory,
    db_crop_job_model,
    loadtest_mode_enabled: bool,
):

    while True:
        try:
            job_id = await job_queue.get()
            console.log(f"[debug]Worker received job: {job_id}[/debug]")

            job_total_counter.inc()

            db: Session = db_session_factory()
            db_job = None
            start_time = datetime.utcnow()
            try:
                db_job = (
                    db.query(db_crop_job_model)
                    .filter(db_crop_job_model.job_id == job_id)
                    .first()
                )

                if not db_job:
                    console.log(
                        f"[warning]Job {job_id} not found in DB, skipping processing.[/warning]"
                    )
                    job_failed_counter.inc()
                    continue

                if db_job.status == "completed":
                    console.log(
                        f"[info]Job {job_id} already completed, skipping reprocessing.[/info]"
                    )
                    job_completed_counter.inc()
                    continue

                if not loadtest_mode_enabled:
                    console.log(
                        f"[info]Simulating processing for job {job_id} (20-second delay)...[/info]"
                    )
                    await asyncio.sleep(20)
                else:
                    console.log(
                        f"[bold magenta]Load testing mode: Skipping artificial delay for job {job_id}.[/bold magenta]"
                    )

                generated_svg_base64, generated_mask_contours_list = (
                    process_image_data_intensive(
                        landmarks_data=db_job.landmarks_json,
                        original_image_base64_bytes=db_job.image_base64.encode("utf-8"),
                        # ,
                        # segmentation_map_base64_bytes=db_job.segmentation_map_base64.encode('utf-8')
                    )
                )

                db_job.svg_base64 = generated_svg_base64
                db_job.mask_contours_json = generated_mask_contours_list
                db_job.status = "completed"
                db_job.completed_at = datetime.utcnow()
                db.add(db_job)
                db.commit()
                db.refresh(db_job)

                console.log(
                    f"[success]Job {job_id} processing completed and results stored.[/success]"
                )
                job_completed_counter.inc()

            except Exception as e:
                console.log(f"[error]Error processing job {job_id}: {e}[/error]")
                if db_job:
                    db_job.status = "failed"
                    db.add(db_job)
                    db.commit()
                db.rollback()
                job_failed_counter.inc()
            finally:
                if db:
                    db.close()
                job_queue.task_done()
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                job_processing_duration_seconds.observe(processing_time)
        except asyncio.CancelledError:
            console.log("[info]Job processing worker task cancelled.[/info]")
            break
        except Exception as e:
            console.log(
                f"[error]Unexpected error in job processing worker: {e}[/error]"
            )
            await asyncio.sleep(1)


async def startup_db_and_worker(app_instance, loadtest_mode_enabled: bool):

    console.log("[info]Creating database tables if they don't exist...[/info]")
    Base.metadata.create_all(bind=engine)
    console.log("[success]Database tables checked/created.[/success]")

    app_instance.state.job_processing_task = asyncio.create_task(
        # Pass the loadtest_mode_enabled flag to the worker
        process_jobs_worker(job_queue, SessionLocal, DBCropJob, loadtest_mode_enabled)
    )
    console.log("[info]Background job processing worker started.[/info]")


async def shutdown_worker(app_instance):

    if hasattr(app_instance.state, "job_processing_task"):
        app_instance.state.job_processing_task.cancel()
        try:
            await app_instance.state.job_processing_task
        except asyncio.CancelledError:
            console.log(
                "[info]Background job processing worker stopped gracefully.[/info]"
            )
        except Exception as e:
            console.log(f"[error]Error stopping worker: {e}[/error]")
