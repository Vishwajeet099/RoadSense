from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

ROAD_CLASSES = {"person", "bicycle", "car", "motorcycle", "bus", "truck"}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("YOLO_CONFIG_DIR", str(PROJECT_ROOT / ".cache" / "ultralytics"))
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".cache" / "matplotlib"))


@dataclass(frozen=True)
class Detection:
    frame_index: int
    class_id: int
    label: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]
    track_id: Optional[int] = None
    is_risk: bool = False


@dataclass(frozen=True)
class RiskEvent:
    frame_index: int
    track_ids: tuple[int, int]
    labels: tuple[str, str]
    reason: str


@dataclass(frozen=True)
class VideoAnalysis:
    detections: list[Detection]
    risk_events: list[RiskEvent]
    annotated_video_path: Optional[Path]
    frame_count: int
    fps: float
    width: int
    height: int

    @property
    def road_users_count(self) -> int:
        track_ids = {detection.track_id for detection in self.detections if detection.track_id is not None}
        return len(track_ids)


@dataclass
class _Track:
    track_id: int
    label: str
    center: tuple[float, float]
    missed_frames: int = 0


@dataclass
class _CentroidTracker:
    max_distance: float
    max_missing_frames: int = 30
    next_track_id: int = 1
    tracks: dict[int, _Track] = field(default_factory=dict)

    def update(self, detections: list[Detection]) -> list[Detection]:
        for track in self.tracks.values():
            track.missed_frames += 1

        assigned_tracks: set[int] = set()
        tracked_detections: list[Detection] = []

        for detection in detections:
            center = _bbox_center(detection.bbox_xyxy)
            track_id = self._best_track_id(detection.label, center, assigned_tracks)
            if track_id is None:
                track_id = self.next_track_id
                self.next_track_id += 1

            self.tracks[track_id] = _Track(
                track_id=track_id,
                label=detection.label,
                center=center,
                missed_frames=0,
            )
            assigned_tracks.add(track_id)
            tracked_detections.append(
                Detection(
                    frame_index=detection.frame_index,
                    class_id=detection.class_id,
                    label=detection.label,
                    confidence=detection.confidence,
                    bbox_xyxy=detection.bbox_xyxy,
                    track_id=track_id,
                    is_risk=detection.is_risk,
                )
            )

        stale_track_ids = [
            track_id
            for track_id, track in self.tracks.items()
            if track.missed_frames > self.max_missing_frames
        ]
        for track_id in stale_track_ids:
            del self.tracks[track_id]

        return tracked_detections

    def _best_track_id(
        self,
        label: str,
        center: tuple[float, float],
        assigned_tracks: set[int],
    ) -> Optional[int]:
        candidates: list[tuple[float, int]] = []
        for track_id, track in self.tracks.items():
            if track_id in assigned_tracks or track.label != label:
                continue
            distance = _distance(center, track.center)
            if distance <= self.max_distance:
                candidates.append((distance, track_id))

        if not candidates:
            return None

        return min(candidates)[1]


def detect_video(
    video_path: Path,
    output_path: Path,
    annotated_video_path: Optional[Path] = None,
    model_name: str = "yolo11n.pt",
    confidence: float = 0.25,
    frame_stride: int = 1,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> VideoAnalysis:
    try:
        import cv2
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError(
            "Install project dependencies before running detection: "
            "python -m pip install -r requirements.txt"
        ) from exc

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    model = YOLO(model_name)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    tracker = _CentroidTracker(max_distance=max(48, min(width, height) * 0.08))
    writer = _create_writer(cv2, annotated_video_path, fps, width, height)
    detections: list[Detection] = []
    risk_events: list[RiskEvent] = []
    frame_index = 0

    while True:
        ok, frame = capture.read()
        if not ok:
            break

        frame_detections: list[Detection] = []
        if frame_index % max(1, frame_stride) == 0:
            results = model.predict(frame, conf=confidence, imgsz=640, verbose=False)
            frame_detections = tracker.update(_extract_road_detections(results, model.names, frame_index))
            frame_risk_events = _find_risk_events(frame_detections)
            risk_track_ids = {
                track_id
                for event in frame_risk_events
                for track_id in event.track_ids
            }
            frame_detections = [
                Detection(
                    frame_index=detection.frame_index,
                    class_id=detection.class_id,
                    label=detection.label,
                    confidence=detection.confidence,
                    bbox_xyxy=detection.bbox_xyxy,
                    track_id=detection.track_id,
                    is_risk=detection.track_id in risk_track_ids,
                )
                for detection in frame_detections
            ]
            detections.extend(frame_detections)
            risk_events.extend(frame_risk_events)
        if writer is not None:
            _draw_detections(cv2, frame, frame_detections)
            writer.write(frame)
        frame_index += 1
        if progress_callback is not None:
            progress_callback(frame_index, total_frames)

    capture.release()
    if writer is not None:
        writer.release()
    if annotated_video_path is not None:
        _convert_to_browser_mp4(annotated_video_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "video": {
                    "source": str(video_path),
                    "frame_count": frame_index,
                    "fps": fps,
                    "width": width,
                    "height": height,
                    "annotated_video_path": str(annotated_video_path) if annotated_video_path else None,
                },
                "summary": {
                    "detections_count": len(detections),
                    "road_users_count": len(
                        {detection.track_id for detection in detections if detection.track_id is not None}
                    ),
                    "risk_events_count": len(risk_events),
                },
                "detections": [asdict(detection) for detection in detections],
                "risk_events": [asdict(event) for event in risk_events],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return VideoAnalysis(
        detections=detections,
        risk_events=risk_events,
        annotated_video_path=annotated_video_path,
        frame_count=frame_index,
        fps=fps,
        width=width,
        height=height,
    )


def _extract_road_detections(results: Iterable[object], names: dict[int, str], frame_index: int) -> list[Detection]:
    frame_detections: list[Detection] = []
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue

        for box in boxes:
            class_id = int(box.cls[0])
            label = names[class_id]
            if label not in ROAD_CLASSES:
                continue

            coords = tuple(float(value) for value in box.xyxy[0].tolist())
            frame_detections.append(
                Detection(
                    frame_index=frame_index,
                    class_id=class_id,
                    label=label,
                    confidence=float(box.conf[0]),
                    bbox_xyxy=coords,
                )
            )
    return frame_detections


def _create_writer(cv2: object, output_path: Optional[Path], fps: float, width: int, height: int) -> object:
    if output_path is None:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not write annotated video: {output_path}")
    return writer


def _convert_to_browser_mp4(output_path: Path) -> None:
    try:
        import imageio_ffmpeg
    except ImportError:
        return

    temp_path = output_path.with_name(f"{output_path.stem}.browser.mp4")
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-i",
        str(output_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(temp_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"Could not convert annotated video for browser playback: {completed.stderr}")
    temp_path.replace(output_path)


def _find_risk_events(detections: list[Detection]) -> list[RiskEvent]:
    risk_events: list[RiskEvent] = []
    for index, first in enumerate(detections):
        if first.track_id is None:
            continue
        for second in detections[index + 1 :]:
            if second.track_id is None:
                continue

            iou = _bbox_iou(first.bbox_xyxy, second.bbox_xyxy)
            center_distance = _distance(_bbox_center(first.bbox_xyxy), _bbox_center(second.bbox_xyxy))
            size_threshold = max(_bbox_diagonal(first.bbox_xyxy), _bbox_diagonal(second.bbox_xyxy)) * 0.7

            reason: Optional[str] = None
            if iou >= 0.02:
                reason = "overlap"
            elif center_distance <= size_threshold:
                reason = "close proximity"

            if reason:
                risk_events.append(
                    RiskEvent(
                        frame_index=first.frame_index,
                        track_ids=(first.track_id, second.track_id),
                        labels=(first.label, second.label),
                        reason=reason,
                    )
                )
    return risk_events


def _draw_detections(cv2: object, frame: object, detections: list[Detection]) -> None:
    for detection in detections:
        x1, y1, x2, y2 = (int(value) for value in detection.bbox_xyxy)
        color = (0, 0, 255) if detection.is_risk else (15, 118, 110)
        label = f"{detection.label}"
        if detection.track_id is not None:
            label = f"{label} #{detection.track_id}"
        label = f"{label} {detection.confidence:.2f}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        text_origin = (x1, max(18, y1 - 8))
        cv2.putText(frame, label, text_origin, cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)


def _bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _bbox_diagonal(bbox: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = bbox
    return _distance((x1, y1), (x2, y2))


def _bbox_iou(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    first_x1, first_y1, first_x2, first_y2 = first
    second_x1, second_y1, second_x2, second_y2 = second

    overlap_x1 = max(first_x1, second_x1)
    overlap_y1 = max(first_y1, second_y1)
    overlap_x2 = min(first_x2, second_x2)
    overlap_y2 = min(first_y2, second_y2)
    overlap_width = max(0, overlap_x2 - overlap_x1)
    overlap_height = max(0, overlap_y2 - overlap_y1)
    overlap_area = overlap_width * overlap_height

    first_area = max(0, first_x2 - first_x1) * max(0, first_y2 - first_y1)
    second_area = max(0, second_x2 - second_x1) * max(0, second_y2 - second_y1)
    union_area = first_area + second_area - overlap_area
    if union_area == 0:
        return 0
    return overlap_area / union_area


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return ((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2) ** 0.5


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RoadSense object detection on a video.")
    parser.add_argument("video", type=Path, help="Path to an input traffic video")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/detections/detections.json"),
        help="JSON file for structured detections",
    )
    parser.add_argument(
        "--annotated-output",
        type=Path,
        default=Path("outputs/videos/annotated.mp4"),
        help="MP4 file for annotated video output",
    )
    parser.add_argument("--model", default="yolo11n.pt", help="Ultralytics model name or local path")
    parser.add_argument("--confidence", type=float, default=0.25, help="Minimum detection confidence")
    args = parser.parse_args()

    analysis = detect_video(args.video, args.output, args.annotated_output, args.model, args.confidence)
    print(f"Wrote {len(analysis.detections)} detections to {args.output}")
    print(f"Wrote annotated video to {analysis.annotated_video_path}")


if __name__ == "__main__":
    main()
