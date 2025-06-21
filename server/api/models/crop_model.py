import json
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, Integer, String, JSON
from sqlalchemy.ext.declarative import declarative_base


class CropData(BaseModel):
    
    image_id: str = Field(
        ..., example="img_12345", description="Unique identifier for the image."
    )
    crop_coordinates: List[float] = Field(
        ...,
        min_items=4,
        max_items=4,
        example=[10.0, 20.0, 100.0, 200.0],
        description="Coordinates of the crop: [x1, y1, x2, y2].",
    )
    processing_options: Optional[Dict[str, Any]] = Field(
        None,
        example={"grayscale": True, "resize_factor": 0.5},
        description="Optional dictionary for additional processing options.",
    )

    class Config:
        orm_mode = True


from database import Base


class DBCropData(Base):
    __tablename__ = "crop_data"
    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(String, unique=True, index=True, nullable=False)
    crop_coordinates_json = Column(String, nullable=False)
    processing_options = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<DBCropData(image_id='{self.image_id}', id={self.id})>"
