# RoadSense Project Explanation

RoadSense is a local traffic video analysis application. In its current working form, it lets a user upload a road/traffic video through a web interface, runs YOLO-based object detection on the uploaded video, assigns lightweight track IDs to detected road users, flags simple proximity/overlap risk events, writes structured JSON results, creates an annotated video with bounding boxes, converts that video to a browser-playable H.264 MP4, and shows the result in the frontend.

This document explains what the project does, how each part works, what files are involved, and what the current limitations are.

## Current Capability

The current end-to-end flow is:

```text
User selects video in browser
  -> Next.js frontend uploads it to FastAPI
  -> FastAPI stores the original file in data/raw/
  -> User clicks Analyze Video
  -> FastAPI starts a background analysis job
  -> Frontend polls job status every 2 seconds
  -> ML detector reads the video with OpenCV
  -> YOLO detects road users on sampled frames
  -> Centroid tracker assigns track IDs
  -> Risk heuristic flags close/overlapping road users
  -> JSON results are saved in outputs/detections/
  -> Annotated MP4 is saved in outputs/videos/
  -> Annotated MP4 is transcoded to H.264 for browser playback
  -> Frontend displays counts, status, paths, and video playback
```

The system is complete for a first demo loop. It is not yet a production-grade traffic intelligence platform or a trained risk-prediction model.

## Repository Structure

```text
RoadSense/
├── backend/
│   └── app/
│       ├── main.py
│       ├── api/routes/
│       │   ├── health.py
│       │   └── videos.py
│       ├── core/config.py
│       ├── schemas/video.py
│       └── services/video_service.py
├── frontend/
│   ├── package.json
│   ├── src/app/page.tsx
│   ├── src/hooks/useVideoAnalysis.ts
│   └── src/lib/types.ts
├── ml/
│   └── detection/detector.py
├── data/
│   ├── raw/
│   ├── processed/
│   └── annotations/
├── outputs/
│   ├── detections/
│   ├── videos/
│   ├── frames/
│   ├── tracks/
│   ├── graphs/
│   └── reports/
├── models/
├── requirements.txt
├── README.md
└── PROJECT_EXPLANATION.md
```

## Main Technologies

The backend uses FastAPI. It provides upload, analysis, polling, health, and annotated-video endpoints.

The frontend uses Next.js, React, TypeScript, Tailwind CSS, and lucide-react icons.

The ML pipeline uses Ultralytics YOLO, OpenCV, NumPy-related scientific packages, and imageio-ffmpeg.

OpenCV reads and writes video frames. Ultralytics YOLO performs object detection. imageio-ffmpeg provides a bundled ffmpeg executable used to convert annotated MP4 files into H.264 video that browsers can play reliably.

## Backend Overview

The backend entry point is:

```text
backend/app/main.py
```

It creates a FastAPI app with:

- Project title: `RoadSense API`
- Description: `AI-powered traffic scene understanding platform`
- Version: `0.1.0`
- CORS enabled for `localhost:3000` and `127.0.0.1:3000`
- Health routes
- Video routes mounted under `/videos`

The backend settings live in:

```text
backend/app/core/config.py
```

Important settings:

- `root_dir`: project root
- `data_raw_dir`: `data/raw`
- `outputs_dir`: `outputs`
- `max_upload_bytes`: 500 MB
- `cors_origins`: frontend dev-server origins

## API Routes

Video routes are defined in:

```text
backend/app/api/routes/videos.py
```

### `POST /videos/upload`

Accepts a video file using multipart form data.

Expected form field:

```text
file
```

Allowed extensions:

```text
.mp4
.mov
.avi
.mkv
.webm
```

The backend saves the file to:

```text
data/raw/<video_id>.<extension>
```

The `video_id` is a generated UUID hex string.

Response shape:

```json
{
  "video_id": "example",
  "filename": "traffic.mp4",
  "path": "/absolute/path/to/data/raw/example.mp4",
  "status": "uploaded"
}
```

### `POST /videos/{video_id}/analyze`

Starts a background analysis job for the uploaded video.

This endpoint does not wait for the entire YOLO run to finish. It creates a thread and returns the current job status quickly.

Possible statuses:

```text
queued
running
complete
failed
not_started
```

Response shape:

```json
{
  "video_id": "example",
  "status": "running",
  "progress": 1,
  "detections_path": null,
  "annotated_video_path": null,
  "annotated_video_url": null,
  "detections_count": 0,
  "road_users_count": 0,
  "risk_events_count": 0,
  "frame_count": 0,
  "fps": 0,
  "message": "Loading YOLO and opening video."
}
```

### `GET /videos/{video_id}/analysis`

Returns the current analysis status.

The frontend polls this endpoint every 2 seconds while analysis is queued or running.

When complete, the response includes:

- JSON output path
- annotated video path
- annotated video URL
- detection count
- road-user count
- risk-event count
- frame count
- FPS

Example complete response:

```json
{
  "video_id": "example",
  "status": "complete",
  "progress": 100,
  "detections_path": "/absolute/path/to/outputs/detections/example.json",
  "annotated_video_path": "/absolute/path/to/outputs/videos/example.mp4",
  "annotated_video_url": "/videos/example/annotated",
  "detections_count": 129,
  "road_users_count": 54,
  "risk_events_count": 33,
  "frame_count": 364,
  "fps": 29.97002997002997,
  "message": "Analysis complete. Detection, basic tracking, annotated video, and risk flags are ready."
}
```

### `GET /videos/{video_id}/annotated`

Streams the annotated MP4 file.

The route supports byte-range requests through the HTTP `Range` header. This is important because browser video players often request only parts of a video while loading, seeking, or showing metadata.

If the browser sends:

```text
Range: bytes=0-1023
```

the backend returns:

```text
206 Partial Content
Accept-Ranges: bytes
Content-Range: bytes 0-1023/<file_size>
Content-Type: video/mp4
```

Without a range header, it returns a normal `FileResponse` with:

```text
Content-Type: video/mp4
Accept-Ranges: bytes
```

## Backend Service Layer

The main backend business logic is in:

```text
backend/app/services/video_service.py
```

### Upload Storage

`save_upload(file)` validates the file extension, creates a video ID, and writes the uploaded file in 1 MB chunks.

It tracks upload size while writing. If the upload exceeds 500 MB, it deletes the partial file and returns HTTP 413.

### Job Management

The analysis job state is stored in memory:

```python
_jobs: dict[str, dict[str, str | int | float | None]] = {}
_jobs_lock = Lock()
```

The lock prevents multiple threads from modifying job state at the same time.

Because jobs are stored in memory, restarting the backend clears active job status. Existing output files remain on disk.

### Starting Analysis

`start_video_analysis(video_id)`:

1. Finds the uploaded video in `data/raw`.
2. Checks whether there is already a queued/running job for that video.
3. Creates a queued job record.
4. Starts a daemon thread.
5. Returns the current job status.

### Running Analysis

`_run_analysis_job(video_id, video_path)`:

1. Builds output paths:
   - `outputs/detections/<video_id>.json`
   - `outputs/videos/<video_id>.mp4`
2. Marks the job as running.
3. Calls `detect_video(...)`.
4. Updates progress whenever frames are processed.
5. On success, marks the job complete and stores counts/paths.
6. On failure, marks the job failed and stores the error message.

The backend currently runs analysis with:

```python
frame_stride=5
```

That means YOLO is run on every 5th frame. All frames are still written to the annotated output video, but only sampled frames receive fresh detections.

This makes demo analysis much faster, especially for 4K videos.

## ML Pipeline

The ML pipeline is currently implemented in:

```text
ml/detection/detector.py
```

This file contains:

- Detection data model
- Risk event data model
- Video analysis result model
- Centroid tracker
- YOLO video processing function
- Detection extraction
- Risk-event heuristic
- Drawing functions
- Browser MP4 conversion
- CLI entry point

## ML Data Models

### `Detection`

Represents one detected road user in one frame.

Fields:

- `frame_index`: zero-based frame number
- `class_id`: YOLO class ID
- `label`: class name such as `car` or `person`
- `confidence`: YOLO confidence score
- `bbox_xyxy`: bounding box as `(x1, y1, x2, y2)`
- `track_id`: lightweight persistent ID
- `is_risk`: whether this detection is involved in a risk event

### `RiskEvent`

Represents a simple conflict/risk event between two tracked detections.

Fields:

- `frame_index`: frame where the event was seen
- `track_ids`: pair of involved track IDs
- `labels`: pair of involved object classes
- `reason`: either `overlap` or `close proximity`

### `VideoAnalysis`

Represents the complete in-memory analysis result.

Fields:

- `detections`
- `risk_events`
- `annotated_video_path`
- `frame_count`
- `fps`
- `width`
- `height`

It also has a computed `road_users_count` property. This counts unique non-null track IDs.

## YOLO Detection

The detector uses:

```python
YOLO("yolo11n.pt")
```

The first time it runs, Ultralytics may download `yolo11n.pt`. After that, the model file is reused locally.

The detector filters YOLO output to road-relevant classes only:

```text
person
bicycle
car
motorcycle
bus
truck
```

All other classes are ignored.

The confidence threshold defaults to:

```text
0.25
```

The inference image size is:

```text
640
```

This keeps inference faster on large videos such as 4K footage.

## Video Reading

OpenCV opens the input video:

```python
capture = cv2.VideoCapture(str(video_path))
```

The detector reads:

- FPS
- total frame count
- frame width
- frame height

If OpenCV cannot open the file, the detector raises:

```text
Could not open video
```

## Frame Sampling

The detector supports `frame_stride`.

If `frame_stride=5`, YOLO runs on frames:

```text
0, 5, 10, 15, ...
```

Frames between those sampled frames are still written into the annotated video, but they do not receive newly drawn boxes unless detection was run on that exact frame.

This is a speed/accuracy tradeoff:

- Smaller stride means more accurate/continuous annotations but slower runtime.
- Larger stride means faster runtime but fewer annotated frames.

## Tracking

RoadSense currently uses a lightweight centroid tracker.

It is implemented as `_CentroidTracker`.

Each detection box is converted to a center point:

```text
center_x = (x1 + x2) / 2
center_y = (y1 + y2) / 2
```

For each new detection, the tracker searches for an existing track with:

- the same class label
- a center point close enough to the new detection
- no assignment already made in the current frame

The maximum matching distance is:

```python
max(48, min(width, height) * 0.08)
```

On a 1920x1080 video, this is about:

```text
86 pixels
```

On a 3840x2160 video, this is about:

```text
173 pixels
```

If no existing track matches, a new track ID is created.

Tracks can survive missed detections for:

```text
30 frames
```

After that, stale tracks are removed.

This tracker is good enough for a first demo, but it is not ByteTrack, DeepSORT, or a production multi-object tracker.

## Risk Event Logic

Risk scoring is currently heuristic.

The detector compares every pair of tracked detections in a sampled frame.

For each pair, it calculates:

- Intersection over union, also called IoU
- Center distance
- Bounding-box diagonal sizes

An event is flagged if either condition is true:

```text
IoU >= 0.02
```

or:

```text
center_distance <= max(box_diagonal_1, box_diagonal_2) * 0.7
```

If IoU condition is true, the reason is:

```text
overlap
```

If proximity condition is true, the reason is:

```text
close proximity
```

Detections involved in risk events are marked with:

```python
is_risk = True
```

In the annotated video:

- normal detections are drawn in teal
- risk detections are drawn in red

This is not a trained accident-risk model. It is a simple first-stage visual warning system.

## Annotated Video Generation

The detector writes an annotated video if `annotated_video_path` is provided.

OpenCV initially writes the video with:

```python
cv2.VideoWriter_fourcc(*"mp4v")
```

Each detection is drawn with:

- bounding box rectangle
- class label
- track ID
- confidence score

Example label:

```text
car #12 0.84
```

After OpenCV finishes writing, the video is converted to browser-friendly H.264.

## Browser MP4 Conversion

Browser playback was unreliable with raw OpenCV `mp4v` output. To fix this, RoadSense uses `imageio-ffmpeg`.

The conversion command is equivalent to:

```bash
ffmpeg -y \
  -i input.mp4 \
  -c:v libx264 \
  -preset veryfast \
  -pix_fmt yuv420p \
  -movflags +faststart \
  -an \
  output.browser.mp4
```

Important details:

- `libx264` creates H.264 video.
- `yuv420p` improves browser compatibility.
- `+faststart` moves MP4 metadata so playback can start before downloading the whole file.
- `-an` removes audio because RoadSense currently does not need audio.

The temporary browser MP4 replaces the original annotated output path.

## JSON Output

Each analysis writes:

```text
outputs/detections/<video_id>.json
```

The JSON has four top-level sections:

```json
{
  "video": {},
  "summary": {},
  "detections": [],
  "risk_events": []
}
```

### `video`

Contains:

- source video path
- frame count
- FPS
- width
- height
- annotated video path

### `summary`

Contains:

- detections count
- road users count
- risk events count

### `detections`

Each detection contains:

- frame index
- YOLO class ID
- label
- confidence
- bounding box
- track ID
- risk flag

### `risk_events`

Each risk event contains:

- frame index
- involved track IDs
- involved labels
- reason

## Frontend Overview

The main frontend screen is:

```text
frontend/src/app/page.tsx
```

It is a client component because it uses React state, file input, fetch calls, and progress polling.

The page has:

- RoadSense header
- upload button
- hidden file input
- analysis queue panel
- selected filename display
- generated video ID display
- Analyze Video button
- progress bar
- status/result text
- annotated output video player
- metric cards for videos, road users, and risk events

## Frontend Upload Behavior

When the user clicks Upload Video, the page opens a hidden file input.

When a file is selected:

1. The selected file is stored in local component state.
2. The upload hook sends the file to `POST /videos/upload`.
3. The backend returns a `video_id`.
4. The UI displays the selected filename and video ID.
5. The Videos metric becomes `1`.

The frontend accepts:

```text
video/*
```

The backend still enforces the actual allowed extension list.

## Frontend Analysis Behavior

When the user clicks Analyze Video:

1. The frontend calls `POST /videos/{video_id}/analyze`.
2. The backend starts the background job.
3. The frontend enters analyzing state.
4. It polls `GET /videos/{video_id}/analysis` every 2 seconds.
5. While running, it shows a progress bar and backend message.
6. When complete, it shows counts and output path.
7. It renders the annotated video player.

## Frontend Hook

The hook is:

```text
frontend/src/hooks/useVideoAnalysis.ts
```

It manages:

- `upload`
- `analysis`
- `isUploading`
- `isAnalyzing`
- combined `isLoading`

It exposes:

- `uploadVideo(file)`
- `analyzeVideo(videoId)`
- `refreshAnalysis(videoId)`

Polling uses:

```text
2 second interval
```

Polling stops when status is:

```text
complete
failed
```

## Frontend Types

Types live in:

```text
frontend/src/lib/types.ts
```

`UploadResponse` mirrors the backend upload schema.

`AnalysisResponse` mirrors the backend analysis schema and includes:

- status
- progress
- output paths
- annotated video URL
- counts
- frame metadata
- message

## Video Playback

The frontend renders:

```tsx
<video controls playsInline preload="metadata">
  <source src={annotatedVideoUrl} type="video/mp4" />
</video>
```

The annotated URL is built as:

```text
http://localhost:8000/videos/<video_id>/annotated?v=<video_id>
```

The query parameter is cache busting. It prevents the browser from reusing an old failed or stale video response.

Playback depends on:

- backend range support
- MP4 content type
- H.264 codec
- yuv420p pixel format
- faststart metadata

These are now handled.

## Data Directories

### `data/raw`

Stores original uploaded videos.

Example:

```text
data/raw/e36ec2e827104c8dabbae5e5fe25b15e.mp4
```

### `data/processed`

Reserved for future transformed data.

### `data/annotations`

Reserved for future ground-truth labels.

## Output Directories

### `outputs/detections`

Stores structured detection JSON files.

Example:

```text
outputs/detections/e36ec2e827104c8dabbae5e5fe25b15e.json
```

### `outputs/videos`

Stores annotated videos.

Example:

```text
outputs/videos/e36ec2e827104c8dabbae5e5fe25b15e.mp4
```

These MP4s are converted to browser-playable H.264 after analysis.

### Other Output Folders

The following folders exist for future phases:

- `outputs/frames`
- `outputs/tracks`
- `outputs/graphs`
- `outputs/reports`

## Model Files

Ultralytics downloads YOLO weights such as:

```text
yolo11n.pt
```

The `.gitignore` excludes model weight files:

```text
*.pt
*.pth
*.onnx
```

This prevents large model artifacts from being committed.

## Environment Variables

When running backend or ML commands, use:

```bash
YOLO_CONFIG_DIR=.cache/ultralytics
MPLCONFIGDIR=.cache/matplotlib
```

These keep Ultralytics and Matplotlib cache/config files inside the project instead of trying to write to restricted macOS user cache paths.

Use:

```bash
PYTHONPATH=backend
```

when starting FastAPI from the project root.

The backend service also inserts the project root into `sys.path` so the backend can import the repo-level `ml` package.

## Running The Project

Start the backend:

```bash
cd /Users/vishwajeet/Desktop/Projects/RoadSense
source .venv/bin/activate

PYTHONPATH=backend YOLO_CONFIG_DIR=.cache/ultralytics MPLCONFIGDIR=.cache/matplotlib \
fastapi dev backend/app/main.py --host 127.0.0.1 --port 8000
```

Start the frontend in a second terminal:

```bash
cd /Users/vishwajeet/Desktop/Projects/RoadSense/frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open:

```text
http://127.0.0.1:3000
```

API docs:

```text
http://127.0.0.1:8000/docs
```

## Testing With The Root MP4

The project root contains:

```text
12165308-uhd_3840_2160_30fps.mp4
```

It was checked with OpenCV:

- format: MP4
- size: about 35 MB
- resolution: 3840x2160
- FPS: about 29.97
- frames: 364
- readable first frame: yes

A sampled YOLO check produced:

- detections: 129
- road users: 54
- risk events: 33

This confirms the video is suitable for RoadSense.

## CLI Detection

You can run detection without the frontend:

```bash
cd /Users/vishwajeet/Desktop/Projects/RoadSense
source .venv/bin/activate

YOLO_CONFIG_DIR=.cache/ultralytics MPLCONFIGDIR=.cache/matplotlib \
python -m ml.detection.detector \
  12165308-uhd_3840_2160_30fps.mp4 \
  --output outputs/detections/manual.json \
  --annotated-output outputs/videos/manual.mp4
```

The CLI prints:

```text
Wrote <n> detections to outputs/detections/manual.json
Wrote annotated video to outputs/videos/manual.mp4
```

## Performance Expectations

For the 35 MB 4K root MP4:

- upload to localhost should usually take a few seconds
- upload should not take minutes
- analysis can take longer because the video is 4K
- with `frame_stride=5`, YOLO processes about 73 of 364 frames
- a normal CPU-only analysis may take roughly 1 to 5 minutes

If upload takes more than about 30 seconds on localhost, the frontend or backend likely needs a restart.

If analysis takes more than about 10 minutes for this short file, the backend likely crashed or is stuck.

## Important Fixes Already Made

### Upload Looked Stuck

Originally the frontend used one `isLoading` state for both upload and analysis. That made analysis look like upload was still happening.

Now the frontend separates:

- `isUploading`
- `isAnalyzing`

### Analysis Blocked The Browser

Originally the Analyze endpoint ran YOLO directly inside the HTTP request. Long videos made the browser wait and look frozen.

Now analysis runs in a background thread and the frontend polls progress.

### Backend Could Not Import `ml`

FastAPI's CLI sometimes used `backend` as the import root, so `ml` was not visible.

The backend service now inserts the project root into `sys.path` before importing `ml.detection.detector`.

### Annotated Video Would Not Play

OpenCV-created MP4 files used `mp4v`, which can be valid but browser-hostile.

Now annotated videos are converted to:

```text
H.264 / avc1
yuv420p
faststart
```

The backend also supports byte-range streaming.

## Current Limitations

Tracking is basic. It uses centroid matching, not ByteTrack or DeepSORT.

Road-user count is based on unique lightweight track IDs. It can overcount if an object disappears/reappears or if the tracker loses it.

Risk events are heuristic. They are not trained predictions and do not calculate true time-to-collision.

Frame sampling means detections are not drawn on every frame. This improves speed but reduces visual continuity.

The background job store is in memory. If the backend restarts, active job status is lost, though files already written to disk remain.

The frontend currently shows only the latest uploaded video in the current page session.

There is no database.

There is no authentication.

There is no persistent job queue.

There is no cancellation endpoint for long-running analysis.

There is no full analytics dashboard yet.

Scene graph, training, evaluation, and risk-model folders are placeholders for future phases.

## Future Improvements

Recommended next improvements:

1. Add real ByteTrack integration for stronger tracking.
2. Add per-frame interpolation so boxes persist visually between sampled frames.
3. Add a proper job queue such as Celery, RQ, or FastAPI background tasks with persistent storage.
4. Store job metadata in SQLite or Postgres.
5. Add a results page for previous videos.
6. Add downloadable JSON and MP4 links.
7. Add trajectory extraction in `ml/features/trajectory.py`.
8. Add speed and direction estimates.
9. Add TTC calculations in `ml/risk/ttc.py`.
10. Add a trained risk classifier in `ml/risk/risk_model.py`.
11. Add scene graph generation in `ml/scene_graph/builder.py`.
12. Add evaluation scripts and metrics.
13. Add tests for upload, analysis jobs, detector JSON output, and video streaming.
14. Add video downscaling options for faster CPU-only analysis.

## Summary

RoadSense currently works as a local, first-stage traffic video analysis demo.

It can:

- accept uploaded videos
- detect vehicles and pedestrians
- assign simple track IDs
- count tracked road users
- flag simple proximity/overlap risk events
- save structured JSON
- produce annotated videos
- stream browser-playable annotated MP4 output

The most important thing to understand is that the project currently has a real perception pipeline but a simple reasoning layer. YOLO detection is real. Video IO is real. Annotated output is real. The tracking and risk scoring are intentionally lightweight first versions that should be replaced with stronger methods as the project matures.
