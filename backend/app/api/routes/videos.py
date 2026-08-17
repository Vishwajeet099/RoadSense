from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.schemas.video import AnalysisResponse, UploadResponse
from app.services.video_service import (
    get_analysis_status,
    get_annotated_video_path,
    save_upload,
    start_video_analysis,
)

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...)) -> UploadResponse:
    stored_video = await save_upload(file)
    return UploadResponse(**stored_video)


@router.post("/{video_id}/analyze", response_model=AnalysisResponse)
def analyze_video(video_id: str) -> AnalysisResponse:
    analysis = start_video_analysis(video_id)
    return AnalysisResponse(**analysis)


@router.get("/{video_id}/analysis", response_model=AnalysisResponse)
def analysis_status(video_id: str) -> AnalysisResponse:
    analysis = get_analysis_status(video_id)
    return AnalysisResponse(**analysis)


@router.get("/{video_id}/annotated")
def annotated_video(video_id: str, range_header: Optional[str] = Header(default=None, alias="Range")):
    video_path = get_annotated_video_path(video_id)
    if range_header:
        return _range_response(video_path, range_header)
    return FileResponse(video_path, media_type="video/mp4", headers={"Accept-Ranges": "bytes"})


def _range_response(video_path: Path, range_header: str) -> StreamingResponse:
    file_size = video_path.stat().st_size
    range_value = range_header.removeprefix("bytes=")
    start_text, _, end_text = range_value.partition("-")

    try:
        start = int(start_text) if start_text else 0
        end = int(end_text) if end_text else file_size - 1
    except ValueError as exc:
        raise HTTPException(status_code=416, detail="Invalid byte range") from exc

    end = min(end, file_size - 1)
    if start > end or start >= file_size:
        raise HTTPException(status_code=416, detail="Requested range is not satisfiable")

    chunk_size = end - start + 1

    def iter_file():
        with video_path.open("rb") as video:
            video.seek(start)
            remaining = chunk_size
            while remaining > 0:
                chunk = video.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        iter_file(),
        status_code=206,
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(chunk_size),
        },
    )
