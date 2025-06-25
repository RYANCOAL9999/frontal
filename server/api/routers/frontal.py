import uuid
import asyncio
from typing import Dict
from datetime import datetime
from functools import lru_cache
from sqlalchemy.orm import Session
from services.logger import console
from drivers.database import get_db, SessionLocal
from fastapi import APIRouter, HTTPException, status, Depends
from models.crop_model import SubmitPayload, JobResponse, JobStatusResponse, DBCropJob

# This module handles the API endpoints for submitting and checking the status of frontal crop processing jobs.
router = APIRouter(
    tags=["Frontal Crop Processing"],
)

# A queue to manage crop processing jobs asynchronously
job_queue: asyncio.Queue = asyncio.Queue()

# Maximum size for the LRU cache to store job data
LRU_CACHE_MAXSIZE = 128


# Helper function to get job data from DB, intended to be cached with background task.
@lru_cache(maxsize=LRU_CACHE_MAXSIZE)
def _get_job_data_from_db_cached(job_id: str) -> Dict[str, str]:

    db = SessionLocal()  # Create a new session for this cached call
    try:
        # Query the database for the job with the given job_id
        db_job = db.query(DBCropJob).filter(DBCropJob.job_id == job_id).first()
        if db_job:
            # Prepare a dictionary that can be used to construct the Pydantic model
            return {
                "id": db_job.job_id,
                "status": db_job.status,
                "svg": db_job.svg_base64,
                "mask_contours": db_job.mask_contours_json,
                "error": (
                    None if db_job.status != "failed" else "Job processing failed."
                ),  # Dummy error msg
            }
        return None
    finally:
        db.close()


# crop submission endpoint
@router.post(
    "/crop/submit",
    response_model=JobResponse,
    summary="Submit a frontal crop for asynchronous processing",
)
async def submit_frontal_crop(
    payload: SubmitPayload, db: Session = Depends(get_db)
) -> JobResponse:
    try:
        # Clear the LRU cache to ensure fresh data
        _get_job_data_from_db_cached.cache_clear()
        console.log("[info]LRU cache for job status cleared.[/info]")

        # Check if the image is already processed and cached
        existing_completed_job = (
            db.query(DBCropJob)
            .filter(
                DBCropJob.image_base64 == payload.image, DBCropJob.status == "completed"
            )
            .first()
        )

        # If an identical image has been processed, return the cached job ID
        if existing_completed_job:
            console.log(
                f"[success]Identical image already processed (Job ID: {existing_completed_job.job_id}). Returning cached result.[/success]"
            )
            return JobResponse(id=existing_completed_job.job_id, status="completed")

        # If the image is not cached, create a new job
        new_job_id = str(uuid.uuid4())

        # Create a new crop job entry in the database
        db_job = DBCropJob(
            job_id=new_job_id,
            image_base64=payload.image,
            landmarks_json=[p.dict() for p in payload.landmarks],
            segmentation_map_base64=payload.segmentation_map,
            status="pending",
            created_at=datetime.utcnow(),
        )
        db.add(db_job)
        db.commit()  # Commit the new job to the database
        db.refresh(db_job)  # Refresh the job to get the latest state

        # Add the new job ID to the job queue for processing
        await job_queue.put(new_job_id)
        console.log(f"[info]Job {new_job_id} submitted and added to queue.[/info]")

        # Return the job response with the new job ID
        return JobResponse(id=new_job_id, status="pending")

    except Exception as e:
        # Rollback the database session in case of an error
        db.rollback()
        console.log(f"[error]An error occurred during job submission: {e}[/error]")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during job submission: {str(e)}",
        )


# get crop status endpoint
@router.get(
    "/crop/status/{job_id}",
    response_model=JobStatusResponse,
    summary="Retrieve the status and results of a crop processing job",
)
async def get_crop_job_status(
    job_id: str, db: Session = Depends(get_db)
) -> JobStatusResponse:

    # Attempt to retrieve job data using the LRU cached helper function
    job_data_dict = _get_job_data_from_db_cached(job_id)

    # If the job data is not found in the cache, query the database directly
    if not job_data_dict:
        console.log(f"[warning]Job with ID '{job_id}' not found.[/warning]")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found.",
        )

    # If the job is still pending, return the status
    console.log(
        f"[info]Retrieving status for job {job_id}. Status: {job_data_dict['status']}[/info]"
    )
    return JobStatusResponse(**job_data_dict)
