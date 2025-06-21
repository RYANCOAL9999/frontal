import json
from rich import print
from database import get_db
from typing import Dict, Any
from functools import lru_cache
from sqlalchemy.orm import Session
from models.crop_model import CropData, DBCropData
from fastapi import APIRouter, HTTPException, status, Depends

router = APIRouter(
    tags=["Frontal Crop"],
)

LRU_CACHE_MAXSIZE = 128


@router.post("/crop/submit", summary="Submit a frontal crop for processing")
async def submit_frontal_crop(data: CropData, db: Session = Depends(get_db)):
    try:
        get_frontal_crop_cached.cache_clear()
        print("LRU cache cleared for get_frontal_crop.")

        existing_crop = (
            db.query(DBCropData).filter(DBCropData.image_id == data.image_id).first()
        )

        if existing_crop:
            print(
                f"Data for image_id: {data.image_id} already exists in DB. Reusing cached data."
            )
            return {
                "message": "Frontal crop already processed, retrieving from cache!",
                "received_data": CropData(
                    image_id=existing_crop.image_id,
                    crop_coordinates=json.loads(existing_crop.crop_coordinates_json),
                    processing_options=existing_crop.processing_options,
                ).dict(),
                "status": "cached",
            }

        crop_coordinates_json_str = json.dumps(data.crop_coordinates)

        db_crop_data = DBCropData(
            image_id=data.image_id,
            crop_coordinates_json=crop_coordinates_json_str,
            processing_options=data.processing_options,
        )
        db.add(db_crop_data)
        db.commit()
        db.refresh(db_crop_data)

        print(f"Stored new crop data for image_id: {data.image_id} in PostgreSQL.")

        return {
            "message": "Frontal crop submitted and stored successfully in PostgreSQL!",
            "received_data": CropData(
                image_id=db_crop_data.image_id,
                crop_coordinates=json.loads(db_crop_data.crop_coordinates_json),
                processing_options=db_crop_data.processing_options,
            ).dict(),
            "status": "stored",
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during submission: {str(e)}",
        )


@lru_cache(maxsize=LRU_CACHE_MAXSIZE)
def _get_crop_data_from_db_cached(image_id: str, db_session_factory):

    db = db_session_factory()
    try:
        db_crop_data = (
            db.query(DBCropData).filter(DBCropData.image_id == image_id).first()
        )
        if db_crop_data:
            return {
                "image_id": db_crop_data.image_id,
                "crop_coordinates": json.loads(db_crop_data.crop_coordinates_json),
                "processing_options": db_crop_data.processing_options,
            }
        return None
    finally:
        db.close()


@router.get(
    "/crop/{image_id}",
    summary="Retrieve crop data by image ID from PostgreSQL (cached)",
)
async def get_frontal_crop_cached(image_id: str, db: Session = Depends(get_db)):
    cached_data = _get_crop_data_from_db_cached(
        image_id, db_session_factory=db.bind.metadata.bind.SessionLocal
    )

    if cached_data:
        print(
            f"Retrieved crop data for image_id: {image_id} from LRU cache or PostgreSQL."
        )

        return {
            "message": "Crop data retrieved successfully!",
            "crop_data": CropData(**cached_data).dict(),
        }
    else:
        print(
            f"No crop data found for image_id: {image_id} in LRU cache or PostgreSQL."
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No crop data found for image ID: {image_id}",
        )
