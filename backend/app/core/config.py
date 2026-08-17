from pathlib import Path


class Settings:
    app_name = "RoadSense API"
    root_dir = Path(__file__).resolve().parents[3]
    data_raw_dir = root_dir / "data" / "raw"
    outputs_dir = root_dir / "outputs"
    max_upload_bytes = 500 * 1024 * 1024
    cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]


settings = Settings()
