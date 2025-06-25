import asyncio
from datetime import datetime
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

# Import the image processing function
# This block attempts to import the compiled Cython module first from the new path.
# If the Cython module (image_processor.so/.pyd within exlib/pyc) is found and successfully imported,
# it will use that for performance.
# If an ImportError occurs, it will fall back to importing the
# pure Python version of image_processor.py from exlib/py.
#
# IMPORTANT: Ensure your project structure includes:
# - exlib/
# - exlib/__init__.py (empty file)
# - exlib/pyc/
# - exlib/pyc/__init__.py (empty file)
# - exlib/pyc/image_processor.pyx (your Cython source)
# - exlib/py/
# - exlib/py/__init__.py (empty file)
# - exlib/py/image_processor.py (your pure Python source)
#
# After compiling image_processor.pyx, the compiled .so/.pyd file will appear
# alongside image_processor.pyx in exlib/pyc.
try:
    from exlib.pyc.image_processor import process_image_data_intensive

    console.log(
        "[bold green]Successfully imported Cythonized image_processor from exlib.pyc.[/bold green]"
    )
except ImportError:
    # Fallback to pure Python version if Cython module is not found.
    from exlib.py.image_processor import process_image_data_intensive

    console.log(
        "[bold yellow]Cythonized image_processor not found. Using pure Python version from exlib.py.[/bold yellow]"
    )


# Background Job Processing Worker
async def process_jobs_worker(
    job_queue: asyncio.Queue,
    db_session_factory,
    db_crop_job_model,
    loadtest_mode_enabled: bool,
) -> None:

    # Start the worker loop to process jobs from the queue
    while True:

        try:
            # Wait for a job from the queue
            job_id = await job_queue.get()
            console.log(f"[debug]Worker received job: {job_id}[/debug]")

            # Increment the total job counter
            job_total_counter.inc()

            # Create a new database session for this job
            db: Session = db_session_factory()
            db_job = None
            start_time = datetime.utcnow()

            try:
                # Fetch the job from the database using the provided job_id
                db_job = (
                    db.query(db_crop_job_model)
                    .filter(db_crop_job_model.job_id == job_id)
                    .first()
                )

                # If the job is not found, log a warning and skip processing
                if not db_job:
                    console.log(
                        f"[warning]Job {job_id} not found in DB, skipping processing.[/warning]"
                    )
                    job_failed_counter.inc()
                    continue

                # If the job is already completed, log and skip reprocessing
                if db_job.status == "completed":
                    console.log(
                        f"[info]Job {job_id} already completed, skipping reprocessing.[/info]"
                    )
                    job_completed_counter.inc()
                    continue

                # If the job is in progress, log and skip reprocessing
                if not loadtest_mode_enabled:
                    console.log(
                        f"[info]Simulating processing for job {job_id} (20-second delay)...[/info]"
                    )
                    await asyncio.sleep(20)
                else:
                    # In load testing mode, skip the artificial delay
                    console.log(
                        f"[bold magenta]Load testing mode: Skipping artificial delay for job {job_id}.[/bold magenta]"
                    )

                # Process the image data using the imported function
                generated_svg_base64, generated_mask_contours_list = (
                    process_image_data_intensive(
                        loadtest_mode_enabled,
                        landmarks_data=db_job.landmarks_json,
                        original_image_base64_bytes=db_job.image_base64.encode("utf-8"),
                        # ,
                        # segmentation_map_base64_bytes=db_job.segmentation_map_base64.encode('utf-8')
                    )
                )

                # Convert the mask contours to SVG path format
                db_job.svg_base64 = generated_svg_base64
                db_job.mask_contours_json = generated_mask_contours_list
                db_job.status = "completed"
                db_job.completed_at = datetime.utcnow()
                db.add(db_job)
                db.commit()
                db.refresh(db_job)

                # Log the successful processing of the job
                console.log(
                    f"[success]Job {job_id} processing completed and results stored.[/success]"
                )

                # Update the LRU cache with the new job data
                job_completed_counter.inc()

            except Exception as e:
                # Log the error and update the job status to failed
                console.log(f"[error]Error processing job {job_id}: {e}[/error]")
                if db_job:
                    db_job.status = "failed"
                    db.add(db_job)
                    db.commit()
                db.rollback()  # Rollback the transaction in case of an error
                job_failed_counter.inc()  # Update the failed job counter
            finally:
                if db:
                    db.close()
                job_queue.task_done()  # Mark the job as done in the queue

                # Calculate and observe the processing time
                processing_time = (datetime.utcnow() - start_time).total_seconds()

                # observe the processing time in the histogram
                job_processing_duration_seconds.observe(processing_time)

        except asyncio.CancelledError:
            # Log the error of the worker task with asyncio.CancelledError
            console.log("[info]Job processing worker task cancelled.[/info]")
            break
        except Exception as e:
            # Log the error of the worker task with a generic exception
            console.log(
                f"[error]Unexpected error in job processing worker: {e}[/error]"
            )
            await asyncio.sleep(1)


# Startup and Shutdown Functions for the Worker
async def startup_db_and_worker(app_instance, loadtest_mode_enabled: bool) -> None:

    console.log("[info]Creating database tables if they don't exist...[/info]")
    # Create the database tables if they do not exist
    Base.metadata.create_all(bind=engine)
    console.log("[success]Database tables checked/created.[/success]")

    # Initialize the job processing worker
    app_instance.state.job_processing_task = asyncio.create_task(
        # Pass the loadtest_mode_enabled flag to the worker
        process_jobs_worker(job_queue, SessionLocal, DBCropJob, loadtest_mode_enabled)
    )
    console.log("[info]Background job processing worker started.[/info]")


# Shutdown function to cancel the worker task gracefully
async def shutdown_worker(app_instance) -> None:

    # Check if the worker task exists and cancel it
    if hasattr(app_instance.state, "job_processing_task"):
        # Cancel the job processing task
        app_instance.state.job_processing_task.cancel()

        try:
            # Wait for the worker task to finish
            await app_instance.state.job_processing_task
        except asyncio.CancelledError:
            # Log the cancellation of the worker task
            console.log(
                "[info]Background job processing worker stopped gracefully.[/info]"
            )
        except Exception as e:
            # Log any error that occurs while stopping the worker
            console.log(f"[error]Error stopping worker: {e}[/error]")
