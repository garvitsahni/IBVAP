import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "../../services/api";
import { DetectionOverlay, type LiveDetection } from "./DetectionOverlay";

const DETECT_INTERVAL_MS = 500;
const CAPTURE_WIDTH = 640;

export function WebcamFeed() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
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
      .catch(() => {
        setError("Camera access denied or unavailable");
      });
    return () => { if (stream) stream.getTracks().forEach((t) => t.stop()); };
  }, []);

  const captureAndDetect = useCallback(async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    if (video.readyState < 2 || video.videoWidth === 0 || video.videoHeight === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const scale = CAPTURE_WIDTH / video.videoWidth;
    canvas.width = CAPTURE_WIDTH;
    canvas.height = Math.round(video.videoHeight * scale);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

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
        timestamp: new Date().toISOString(),
      })));
    } catch {
      // skip
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
    </div>
  );
}
