export type UploadResponse = {
  video_id: string;
  filename: string;
  path: string;
  status: string;
};

export type AnalysisResponse = {
  video_id: string;
  status: string;
  progress: number;
  detections_path: string | null;
  annotated_video_path: string | null;
  annotated_video_url: string | null;
  detections_count: number;
  road_users_count: number;
  risk_events_count: number;
  frame_count: number;
  fps: number;
  message: string;
};
