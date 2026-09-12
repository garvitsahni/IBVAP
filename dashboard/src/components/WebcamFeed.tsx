import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "../services/api";
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

    // Try to boost exposure for low-light via advanced constraints
    navigator.mediaDevices
      .getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: "environment",
          // Advanced constraints for low-light boost (supported on some webcams)
          advanced: [
            { exposureCompensation: 2.0 },
            { exposureMode: "continuous" },
            { whiteBalanceMode: "continuous" },
            { iso: 800 },
          ] as any[],
        },
        audio: false,
      })
      .then((s) => {
        stream = s;
        video.srcObject = s;
        // Boost and periodically re-apply to fight auto-exposure
        const track = s.getVideoTracks()[0];
        if (track) {
          const applyBoost = () => {
            const caps = track.getCapabilities?.() as any ?? {};
            const constraints: any[] = [];
            if (caps.exposureCompensation) {
              constraints.push({ exposureCompensation: caps.exposureCompensation.max ?? 2.0 });
            }
            if (caps.iso) {
              constraints.push({ iso: caps.iso.max ?? 800 });
            }
            if (constraints.length > 0) {
              track.applyConstraints({ advanced: constraints }).catch(() => {});
            }
          };
          applyBoost();
          // Re-apply every 2 seconds to prevent auto-exposure override
          const boostInterval = setInterval(applyBoost, 2000);
          // Clear interval on stream stop
          track.addEventListener("ended", () => clearInterval(boostInterval));
        }
        setStreaming(true);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Camera access denied");
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
      <div className="w-full h-full flex flex-col items-center justify-center bg-surface-0 text-text-muted gap-2">
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
