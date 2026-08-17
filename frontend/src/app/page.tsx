"use client";

import {
  Activity,
  BarChart3,
  Car,
  CheckCircle2,
  Clock3,
  FileJson,
  Loader2,
  Play,
  Upload,
  Video,
} from "lucide-react";
import { useRef, useState } from "react";

import { useVideoAnalysis } from "@/hooks/useVideoAnalysis";

export default function Home() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { upload, analysis, isUploading, isAnalyzing, isLoading, uploadVideo, analyzeVideo } = useVideoAnalysis();
  const annotatedVideoUrl = analysis?.annotated_video_url
    ? `http://localhost:8000${analysis.annotated_video_url}?v=${analysis.video_id}`
    : null;

  const statusLabel = isUploading
    ? "Uploading"
    : isAnalyzing
      ? "Analyzing"
      : analysis?.status === "complete"
        ? "Complete"
        : upload
          ? "Uploaded"
          : "Idle";

  const metrics = [
    { label: "Videos", value: upload ? "1" : "0", detail: upload ? "ready" : "waiting", icon: Video },
    { label: "Road Users", value: String(analysis?.road_users_count ?? 0), detail: "tracked IDs", icon: Car },
    {
      label: "Risk Events",
      value: String(analysis?.risk_events_count ?? 0),
      detail: "proximity flags",
      icon: Activity,
    },
  ];

  async function handleUpload(file: File) {
    setError(null);
    setSelectedFile(file);
    try {
      await uploadVideo(file);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Video upload failed");
    }
  }

  async function handleAnalyze() {
    if (!upload) {
      return;
    }

    setError(null);
    try {
      await analyzeVideo(upload.video_id);
    } catch (analysisError) {
      setError(analysisError instanceof Error ? analysisError.message : "Video analysis failed");
    }
  }

  return (
    <main className="min-h-screen">
      <header className="border-b border-white/70 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-md bg-asphalt text-lane">
              <BarChart3 size={20} />
            </span>
            <div>
              <h1 className="text-xl font-semibold text-asphalt">RoadSense</h1>
              <p className="text-sm text-zinc-500">Traffic video analysis workspace</p>
            </div>
          </div>

          <button
            className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-signal px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
            disabled={isLoading}
            type="button"
            onClick={() => fileInputRef.current?.click()}
          >
            {isUploading ? <Loader2 className="animate-spin" size={17} /> : <Upload size={17} />}
            {isUploading ? "Uploading..." : "Upload Video"}
          </button>
          <input
            ref={fileInputRef}
            accept="video/*"
            className="hidden"
            type="file"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                void handleUpload(file);
              }
              event.currentTarget.value = "";
            }}
          />
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.75fr)]">
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-3">
            {metrics.map((metric) => {
              const Icon = metric.icon;
              return (
                <div key={metric.label} className="rounded-lg border border-white/80 bg-white/90 p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <span className="text-xs font-semibold uppercase text-zinc-500">{metric.label}</span>
                      <p className="mt-2 text-3xl font-semibold text-asphalt">{metric.value}</p>
                      <p className="mt-1 text-xs text-zinc-500">{metric.detail}</p>
                    </div>
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-teal-50 text-signal">
                      <Icon size={18} />
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="rounded-lg border border-white/80 bg-white/90 p-4 shadow-sm sm:p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-base font-semibold text-asphalt">Analysis Workbench</h2>
                <p className="text-sm text-zinc-500">Upload a road video, run detection, and review annotated output.</p>
              </div>
              <span className="inline-flex w-fit items-center gap-2 rounded-full bg-zinc-100 px-3 py-1 text-xs font-semibold text-zinc-600">
                <span className="h-2 w-2 rounded-full bg-signal" />
                {statusLabel}
              </span>
            </div>

            <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(280px,0.55fr)]">
              <div className="rounded-lg border border-dashed border-zinc-300 bg-[#f8faf9] p-4 sm:p-6">
                <div className="flex min-h-72 flex-col items-center justify-center text-center">
                  <button
                    className="flex h-14 w-14 items-center justify-center rounded-md bg-white text-signal shadow-sm ring-1 ring-zinc-200 transition hover:scale-105 disabled:opacity-60"
                    disabled={isLoading}
                    title="Choose video"
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    {isUploading ? <Loader2 className="animate-spin" size={24} /> : <Upload size={24} />}
                  </button>

                  <p className="mt-4 max-w-full break-words text-sm font-semibold text-asphalt">
                    {selectedFile ? selectedFile.name : "No video selected"}
                  </p>
                  <p className="mt-1 max-w-md text-sm leading-6 text-zinc-500">
                    {upload
                      ? `Uploaded as ${upload.video_id}`
                      : "Choose an MP4, MOV, AVI, MKV, or WebM traffic video."}
                  </p>

                  {error ? (
                    <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm font-medium text-alert">{error}</p>
                  ) : null}

                  <div className="mt-5 flex flex-col gap-3 sm:flex-row">
                    <button
                      className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-zinc-300 bg-white px-4 text-sm font-semibold text-asphalt shadow-sm transition hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={isLoading}
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <Upload size={16} />
                      Select Video
                    </button>
                    <button
                      className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-asphalt px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={!upload || isLoading}
                      type="button"
                      onClick={() => void handleAnalyze()}
                    >
                      {isAnalyzing ? <Loader2 className="animate-spin" size={16} /> : <Play size={16} />}
                      {isAnalyzing ? "Analyzing" : "Analyze Video"}
                    </button>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-zinc-200 bg-white p-4">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold text-asphalt">Job Status</h3>
                  <Clock3 className="text-zinc-400" size={17} />
                </div>

                <div className="mt-4 space-y-4">
                  <div>
                    <div className="mb-2 flex items-center justify-between text-xs font-semibold text-zinc-500">
                      <span>Progress</span>
                      <span>{Math.round(analysis?.progress ?? 0)}%</span>
                    </div>
                    <div className="h-2.5 overflow-hidden rounded-full bg-zinc-200">
                      <div
                        className="h-full rounded-full bg-signal transition-all"
                        style={{ width: `${Math.max(0, Math.min(100, analysis?.progress ?? 0))}%` }}
                      />
                    </div>
                  </div>

                  <div className="rounded-md bg-zinc-50 p-3 text-sm leading-6 text-zinc-600">
                    {analysis?.message ?? "Waiting for a video."}
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-md bg-[#f8faf9] p-3">
                      <p className="text-xs font-semibold uppercase text-zinc-500">Frames</p>
                      <p className="mt-1 font-semibold text-asphalt">{analysis?.frame_count ?? 0}</p>
                    </div>
                    <div className="rounded-md bg-[#f8faf9] p-3">
                      <p className="text-xs font-semibold uppercase text-zinc-500">Detections</p>
                      <p className="mt-1 font-semibold text-asphalt">{analysis?.detections_count ?? 0}</p>
                    </div>
                  </div>

                  {analysis?.status === "complete" ? (
                    <div className="flex items-start gap-2 rounded-md bg-teal-50 p-3 text-sm text-teal-900">
                      <CheckCircle2 className="mt-0.5 shrink-0" size={16} />
                      <span>Analysis output is ready for review.</span>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>

            {annotatedVideoUrl ? (
              <div className="mt-5">
                <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <h3 className="text-sm font-semibold text-asphalt">Annotated Output</h3>
                  {analysis?.detections_path ? (
                    <span className="inline-flex min-w-0 items-center gap-2 rounded-md bg-zinc-100 px-3 py-1 text-xs text-zinc-600">
                      <FileJson size={14} />
                      <span className="truncate">JSON saved</span>
                    </span>
                  ) : null}
                </div>
                <video
                  className="aspect-video w-full rounded-md bg-black shadow-sm ring-1 ring-zinc-200"
                  controls
                  playsInline
                  preload="metadata"
                >
                  <source src={annotatedVideoUrl} type="video/mp4" />
                </video>
                {analysis?.detections_path ? (
                  <p className="mt-3 break-words text-xs text-zinc-500">Saved: {analysis.detections_path}</p>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>

        <aside className="space-y-5">
          <div className="rounded-lg border border-white/80 bg-asphalt p-5 text-white shadow-sm">
            <p className="text-xs font-semibold uppercase text-lane">Pipeline</p>
            <h2 className="mt-2 text-lg font-semibold">Video to scene signals</h2>
            <div className="mt-5 space-y-3">
              {["Upload", "Detect", "Track", "Flag", "Review"].map((step, index) => (
                <div key={step} className="flex items-center gap-3">
                  <span className="flex h-7 w-7 items-center justify-center rounded-md bg-white/10 text-xs font-semibold">
                    {index + 1}
                  </span>
                  <span className="text-sm text-zinc-100">{step}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-white/80 bg-white/90 p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-asphalt">Current Outputs</h2>
            <div className="mt-4 space-y-3 text-sm text-zinc-600">
              <div className="flex items-center justify-between gap-3">
                <span>Detection JSON</span>
                <span className="font-semibold text-asphalt">{analysis?.detections_path ? "Ready" : "Pending"}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span>Annotated MP4</span>
                <span className="font-semibold text-asphalt">{analysis?.annotated_video_url ? "Ready" : "Pending"}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span>Playback Codec</span>
                <span className="font-semibold text-asphalt">H.264</span>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-white/80 bg-white/90 p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-asphalt">Notes</h2>
            <p className="mt-3 text-sm leading-6 text-zinc-600">
              The current demo samples frames for speed, assigns lightweight track IDs, and flags simple proximity
              conflicts. It is designed to make the full workflow visible on a local machine.
            </p>
          </div>
        </aside>
      </section>
    </main>
  );
}
