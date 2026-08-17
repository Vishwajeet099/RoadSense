"use client";

import { useState } from "react";

import type { AnalysisResponse, UploadResponse } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function useVideoAnalysis() {
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  async function uploadVideo(file: File) {
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(`${API_BASE_URL}/videos/upload`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error("Video upload failed");
      }
      const data = (await response.json()) as UploadResponse;
      setUpload(data);
      setAnalysis(null);
      return data;
    } finally {
      setIsUploading(false);
    }
  }

  async function analyzeVideo(videoId: string) {
    setIsAnalyzing(true);
    try {
      const response = await fetch(`${API_BASE_URL}/videos/${videoId}/analyze`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error("Video analysis failed");
      }
      const data = (await response.json()) as AnalysisResponse;
      setAnalysis(data);
      if (data.status === "complete" || data.status === "failed") {
        setIsAnalyzing(false);
        return data;
      }
      return pollAnalysis(videoId);
    } catch (error) {
      setIsAnalyzing(false);
      throw error;
    }
  }

  async function pollAnalysis(videoId: string) {
    while (true) {
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
      const response = await fetch(`${API_BASE_URL}/videos/${videoId}/analysis`);
      if (!response.ok) {
        setIsAnalyzing(false);
        throw new Error("Could not fetch analysis status");
      }
      const data = (await response.json()) as AnalysisResponse;
      setAnalysis(data);
      if (data.status === "complete" || data.status === "failed") {
        setIsAnalyzing(false);
        return data;
      }
    }
  }

  async function refreshAnalysis(videoId: string) {
    const response = await fetch(`${API_BASE_URL}/videos/${videoId}/analysis`);
    if (!response.ok) {
      throw new Error("Could not fetch analysis status");
    }
    const data = (await response.json()) as AnalysisResponse;
    setAnalysis(data);
    if (data.status === "running" || data.status === "queued") {
      setIsAnalyzing(true);
      void pollAnalysis(videoId);
    }
    return data;
  }

  return {
    upload,
    analysis,
    isUploading,
    isAnalyzing,
    isLoading: isUploading || isAnalyzing,
    uploadVideo,
    analyzeVideo,
    refreshAnalysis,
  };
}
