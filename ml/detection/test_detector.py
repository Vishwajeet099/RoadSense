import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("YOLO_CONFIG_DIR", str(PROJECT_ROOT / ".cache" / "ultralytics"))
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".cache" / "matplotlib"))

from ultralytics import YOLO


model = YOLO("yolo11n.pt")
results = model("https://ultralytics.com/images/bus.jpg", save=True)

print(f"Detection complete: {len(results)} result batch")
