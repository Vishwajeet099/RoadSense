# RoadSense

RoadSense is an AI-powered traffic scene understanding project. The first milestone is intentionally practical:

1. Upload or input a traffic video.
2. Detect road users such as vehicles, cyclists, and pedestrians.
3. Track them across frames.
4. Save structured detections and tracks.
5. Visualize the annotated output in a web dashboard.

## Repository Layout

```text
RoadSense/
├── backend/      # FastAPI API for uploads, analysis jobs, and results
├── frontend/     # Next.js dashboard
├── ml/           # Detection, tracking, feature, risk, and scene graph code
├── data/         # Local input data and annotations
├── models/       # Local model artifacts
└── outputs/      # Generated videos, detections, tracks, graphs, and reports
```

## Python Setup

Python 3.11 or 3.12 is recommended for the ML stack. This machine currently reports `python3` as 3.9.6, so install a newer interpreter before the full dependency install if possible.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you only have `python3`, you can still create the environment with:

```bash
python3 -m venv .venv
```

## Backend

```bash
source .venv/bin/activate
fastapi dev backend/app/main.py
```

Useful endpoints:

- `GET /`
- `GET /health`
- `POST /videos/upload`
- `POST /videos/{video_id}/analyze`

## ML Detection

Run YOLO detections on a local video:

```bash
source .venv/bin/activate
python -m ml.detection.detector data/raw/sample.mp4 --output outputs/detections/sample.json
```

The detector keeps road-relevant classes and writes structured JSON detections.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard defaults to the API at `http://localhost:8000`. Override it with `NEXT_PUBLIC_API_BASE_URL` when needed.

## Build Sequence

Phase 1: video input, YOLO detection, annotated output.

Phase 2: ByteTrack-style tracking, persistent IDs, trajectories.

Phase 3: speed, direction, distance, time-to-collision, and conflict detection.

Phase 4: risk classifier and evaluation.

Phase 5: dynamic scene graph.

Phase 6: FastAPI and Next.js analytics dashboard.
