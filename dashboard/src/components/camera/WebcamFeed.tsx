import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "@/services/api";
import { DetectionOverlay, type LiveDetection } from "./DetectionOverlay";

const DETECT_INTERVAL_MS = 500;
const CAPTURE_WIDTH = 640;

export function WebcamFeed() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const inFlightRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [detections, setDetections] = useState<LiveDetection[]>([]);
  const [frameSize, setFrameSize] = useState<{ w: number; h: number } | null>(null);

  useEffect(() => {
    api.seedLocalCamera().catch(() => {});
    const video = videoRef.current;
    if (!video) return;
    let stream: MediaStream | null = null;

    navigator.mediaDevices
      .getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      })
      .then((s) => {
        stream = s;
        video.srcObject = s;
        setStreaming(true);
      })
      .catch((err: unknown) => {
        const name =
          (err as { name?: string } | null)?.name || "UnknownError";
        const detail =
          (err as { message?: string } | null)?.message || "";
        // Surface the real error: the generic text hid whether this is a
        // permission, busy-hardware, or missing-device failure.
        console.error("[WebcamFeed] getUserMedia failed:", name, detail);
        const hint =
          name === "NotAllowedError"
            ? " — allow camera for this site (lock icon) and in Windows Privacy settings"
            : name === "NotReadableError" || name === "AbortError"
              ? " — another app (Teams / Zoom / Camera app / other tab) is holding the camera; close it"
              : name === "NotFoundError" || name === "OverconstrainedError"
                ? " — no usable camera found; check Device Manager / Fn-key toggle"
                : "";
        setError(`Camera unavailable (${name})${hint}`);
      });
    return () => { if (stream) stream.getTracks().forEach((t) => t.stop()); };
  }, []);

  const captureAndDetect = useCallback(async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    // Single-flight: never queue detect requests — overlapping calls got 429s
    // and delayed the NEXT successful response, leaving stale boxes on screen.
    if (inFlightRef.current) return;
    if (video.readyState < 2 || video.videoWidth === 0 || video.videoHeight === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const scale = CAPTURE_WIDTH / video.videoWidth;
    canvas.width = CAPTURE_WIDTH;
    canvas.height = Math.round(video.videoHeight * scale);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Timestamp at CAPTURE time — the overlay's stale filter (3s) must age
    // the frame itself, not the moment a slow response arrived.
    const capturedAt = new Date().toISOString();
    inFlightRef.current = true;
    try {
      const dataUrl = canvas.toDataURL("image/jpeg", 0.8);
      const base64 = dataUrl.split(",")[1];
      if (!base64) return;
      const result = await api.detectFrame(base64, "browser-webcam");
      setFrameSize({ w: result.width, h: result.height });
      setDetections(result.detections.map((d) => ({
        camera_id: result.camera_id,
        object_type: d.class_name,
        bbox: d.bbox,
        confidence: d.confidence,
        timestamp: capturedAt,
        plate_text: (d as any).plate_text || null,
      })));
    } catch {
      // skip (429/network) — in-flight flag released below
    } finally {
      inFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    if (!streaming) return;
    const id = setInterval(captureAndDetect, DETECT_INTERVAL_MS);
    return () => clearInterval(id);
  }, [streaming, captureAndDetect]);

  if (error) {
    return (
      <div className="absolute inset-0 flex flex-col items-center justify-center bg-surface-2 text-text-muted gap-2">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/>
          <circle cx="12" cy="13" r="3"/>
          <line x1="2" y1="2" x2="22" y2="22"/>
        </svg>
        <span className="text-[11px]">{error}</span>
      </div>
    );
  }

  return (
    <div className="absolute inset-0">
      <canvas ref={canvasRef} className="hidden" />
      <video ref={videoRef} className="w-full h-full object-cover" autoPlay muted playsInline />
      <DetectionOverlay
        cameraId="browser-webcam"
        detections={detections}
        videoWidth={frameSize?.w}
        videoHeight={frameSize?.h}
      />
      <div className="absolute bottom-2 left-2 right-2">
        <div className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-text-muted bg-surface-2/80 backdrop-blur rounded border border-border/30">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 16v-4"/>
            <path d="M12 8h.01"/>
          </svg>
          <span>Preview only — no alerts generated</span>
        </div>
      </div>
    </div>
  );
}
