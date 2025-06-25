from datetime import datetime
from drivers.database import Base
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON


# Pydantic models for the crop job submission and response structures
class Point(BaseModel):
    x: float = Field(..., description="X coordinate of the point.")
    y: float = Field(..., description="Y coordinate of the point.")


# Pydantic models for the crop job submission payload and response structures
class SubmitPayload(BaseModel):
    image: str = Field(..., description="Base64 encoded string of the image.")
    landmarks: List[Point] = Field(..., description="List of facial landmark points.")
    segmentation_map: str = Field(
        ..., description="Base64 encoded string of the segmentation map."
    )


# Pydantic model for the job submission response
class JobResponse(BaseModel):
    id: str = Field(..., description="Unique ID of the submitted job.")
    status: str = Field(
        ...,
        description="Current status of the job (e.g., 'pending', 'completed', 'failed').",
    )


# Pydantic model for the mask contour details in the crop result
class MaskContourDetail(BaseModel):
    name: str = Field(
        ...,
        description="Name of the segmented region (e.g., 'right_cheek', 'right_undereye').",
    )
    path_d: str = Field(
        ..., description="SVG path 'd' attribute string for the contour."
    )
    points: List[List[float]] = Field(
        ..., description="List of [x, y] coordinates forming the contour."
    )


# Pydantic model for the crop result response, including SVG and mask contours
class CropResultResponse(BaseModel):
    svg: str = Field(
        ...,
        description="Base64 encoded SVG string of the processed image with clip-paths.",
    )
    mask_contours: List[MaskContourDetail] = Field(
        ..., description="List of detailed mask contours, including SVG path data."
    )


# Pydantic model for the job status response, including SVG and mask contours
class JobStatusResponse(JobResponse):
    svg: Optional[str] = Field(
        None, description="Base64 encoded SVG string, if job is completed."
    )
    mask_contours: Optional[Dict[str, List[List[float]]]] = Field(
        None, description="Dictionary of mask contours, if job is completed."
    )
    error: Optional[str] = Field(None, description="Error message if job failed.")

    class Config:
        orm_mode = True


# This class represents the database model for crop jobs
class DBCropJob(Base):
    __tablename__ = "crop_jobs"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True, nullable=False)

    image_base64 = Column(Text, nullable=False)
    landmarks_json = Column(JSON, nullable=False)
    segmentation_map_base64 = Column(Text, nullable=False)

    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    svg_base64 = Column(Text, nullable=True)
    mask_contours_json = Column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<DBCropJob(job_id='{self.job_id}', status='{self.status}')>"
