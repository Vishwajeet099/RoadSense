from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    video_id: str
    filename: str
    path: str
    status: str


class AnalysisResponse(BaseModel):
    video_id: str
    status: str
    progress: float = 0
    detections_path: Optional[str] = None
    annotated_video_path: Optional[str] = None
    annotated_video_url: Optional[str] = None
    detections_count: int = 0
    road_users_count: int = 0
    risk_events_count: int = 0
    frame_count: int = 0
    fps: float = 0
    message: str
