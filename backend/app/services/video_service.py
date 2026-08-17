from __future__ import annotations

from pathlib import Path
import sys
from threading import Lock, Thread
from time import time
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.core.config import settings

if str(settings.root_dir) not in sys.path:
    sys.path.insert(0, str(settings.root_dir))

from ml.detection.detector import detect_video

ALLOWED_VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
DEFAULT_ANALYSIS = {
    "detections_path": None,
    "annotated_video_path": None,
    "annotated_video_url": None,
    "detections_count": 0,
    "road_users_count": 0,
    "risk_events_count": 0,
    "frame_count": 0,
    "fps": 0,
}
_jobs: dict[str, dict[str, str | int | float | None]] = {}
_jobs_lock = Lock()


async def save_upload(file: UploadFile) -> dict[str, str]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_VIDEO_SUFFIXES:
        raise HTTPException(status_code=400, detail="Unsupported video format")

    settings.data_raw_dir.mkdir(parents=True, exist_ok=True)
    video_id = uuid4().hex
    destination = settings.data_raw_dir / f"{video_id}{suffix}"

    total_size = 0
    with destination.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            total_size += len(chunk)
            if total_size > settings.max_upload_bytes:
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Video upload is too large")
            output.write(chunk)

    return {
        "video_id": video_id,
        "filename": file.filename or destination.name,
        "path": str(destination),
        "status": "uploaded",
    }


def start_video_analysis(video_id: str) -> dict[str, str | int | float | None]:
    matches = list(settings.data_raw_dir.glob(f"{video_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Video not found")

    with _jobs_lock:
        existing_job = _jobs.get(video_id)
        if existing_job and existing_job["status"] in {"queued", "running"}:
            return dict(existing_job)

        _jobs[video_id] = {
            "video_id": video_id,
            "status": "queued",
            "progress": 0,
            **DEFAULT_ANALYSIS,
            "message": "Analysis queued.",
            "started_at": time(),
        }

    worker = Thread(target=_run_analysis_job, args=(video_id, matches[0]), daemon=True)
    worker.start()
    return get_analysis_status(video_id)


def get_analysis_status(video_id: str) -> dict[str, str | int | float | None]:
    with _jobs_lock:
        job = _jobs.get(video_id)
        if job:
            return _public_job(job)

    detections_path = settings.outputs_dir / "detections" / f"{video_id}.json"
    annotated_video_path = settings.outputs_dir / "videos" / f"{video_id}.mp4"
    if detections_path.exists() and annotated_video_path.exists():
        return {
            "video_id": video_id,
            "status": "complete",
            "progress": 100,
            "detections_path": str(detections_path),
            "annotated_video_path": str(annotated_video_path),
            "annotated_video_url": f"/videos/{video_id}/annotated",
            "detections_count": 0,
            "road_users_count": 0,
            "risk_events_count": 0,
            "frame_count": 0,
            "fps": 0,
            "message": "Analysis output exists. Re-run analysis to refresh counts.",
        }

    if not list(settings.data_raw_dir.glob(f"{video_id}.*")):
        raise HTTPException(status_code=404, detail="Video not found")

    return {
        "video_id": video_id,
        "status": "not_started",
        "progress": 0,
        **DEFAULT_ANALYSIS,
        "message": "Analysis has not started.",
    }


def _run_analysis_job(video_id: str, video_path: Path) -> None:
    detections_path = settings.outputs_dir / "detections" / f"{video_id}.json"
    annotated_video_path = settings.outputs_dir / "videos" / f"{video_id}.mp4"

    _update_job(video_id, status="running", progress=1, message="Loading YOLO and opening video.")

    def update_progress(done_frames: int, total_frames: int) -> None:
        if total_frames:
            progress = min(99, max(1, (done_frames / total_frames) * 100))
            _update_job(video_id, progress=round(progress, 1), message=f"Analyzed {done_frames} of {total_frames} frames.")

    try:
        analysis = detect_video(
            video_path=video_path,
            output_path=detections_path,
            annotated_video_path=annotated_video_path,
            frame_stride=5,
            progress_callback=update_progress,
        )
    except FileNotFoundError as exc:
        _update_job(video_id, status="failed", progress=0, message=str(exc))
        return
    except RuntimeError as exc:
        _update_job(video_id, status="failed", progress=0, message=str(exc))
        return

    _update_job(
        video_id,
        status="complete",
        progress=100,
        detections_path=str(detections_path),
        annotated_video_path=str(annotated_video_path),
        annotated_video_url=f"/videos/{video_id}/annotated",
        detections_count=len(analysis.detections),
        road_users_count=analysis.road_users_count,
        risk_events_count=len(analysis.risk_events),
        frame_count=analysis.frame_count,
        fps=analysis.fps,
        message="Analysis complete. Detection, basic tracking, annotated video, and risk flags are ready.",
    )


def get_annotated_video_path(video_id: str) -> Path:
    video_path = settings.outputs_dir / "videos" / f"{video_id}.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Annotated video not found")
    return video_path


def _update_job(video_id: str, **updates: str | int | float | None) -> None:
    with _jobs_lock:
        current_job = _jobs.setdefault(
            video_id,
            {
                "video_id": video_id,
                "status": "queued",
                "progress": 0,
                **DEFAULT_ANALYSIS,
                "message": "Analysis queued.",
            },
        )
        current_job.update(updates)


def _public_job(job: dict[str, str | int | float | None]) -> dict[str, str | int | float | None]:
    return {
        "video_id": job["video_id"],
        "status": job["status"],
        "progress": job.get("progress", 0),
        "detections_path": job.get("detections_path"),
        "annotated_video_path": job.get("annotated_video_path"),
        "annotated_video_url": job.get("annotated_video_url"),
        "detections_count": job.get("detections_count", 0),
        "road_users_count": job.get("road_users_count", 0),
        "risk_events_count": job.get("risk_events_count", 0),
        "frame_count": job.get("frame_count", 0),
        "fps": job.get("fps", 0),
        "message": job.get("message", ""),
    }
