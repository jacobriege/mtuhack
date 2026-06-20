from pydantic import BaseModel
from typing import Any


class ReportData(BaseModel):
    """Flexible container for arbitrary sensor/robot payload fields."""
    model_config = {"extra": "allow"}


class ReportIn(BaseModel):
    robot_id: str
    timestamp: str
    data: ReportData


class ReportOut(BaseModel):
    id: str
    robot_id: str
    timestamp: str
    data: ReportData


class ImageOut(BaseModel):
    id: str
    filename: str
    url: str
