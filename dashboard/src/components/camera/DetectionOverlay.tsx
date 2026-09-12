import { useEffect, useRef, useState } from "react";
import { SSEClient } from "../../services/sse";

export interface LiveDetection {
  camera_id: string;
  object_type: string;
  object_id?: string | null;
  track_id?: string;
  bbox: { x1: number; y1: number; x2: number; y2: number };
  confidence: number;
  timestamp: string;
}

interface ScaledDetection extends LiveDetection {
  sx: number;
  sy: number;
  sw: number;
  sh: number;
}

const STALE_MS = 3000;

function mapBbox(
  bbox: { x1: number; y1: number; x2: number; y2: number },
  srcW: number, srcH: number,
  dispW: number, dispH: number,
): { sx: number; sy: number; sw: number; sh: number } | null {
  if (!srcW || !srcH || !dispW || !dispH) return null;
  const scaleX = dispW / srcW;
  const scaleY = dispH / srcH;
  const scale = Math.max(scaleX, scaleY);
  const oX = (dispW - srcW * scale) / 2;
  const oY = (dispH - srcH * scale) / 2;
  const sx = oX + bbox.x1 * scale;
  const sy = oY + bbox.y1 * scale;
  const sw = (bbox.x2 - bbox.x1) * scale;
  const sh = (bbox.y2 - bbox.y1) * scale;
  if (sw <= 0 || sh <= 0) return null;
  return { sx, sy, sw, sh };
}

interface Props {
  cameraId: string;
  detections?: LiveDetection[];
  videoWidth?: number;
  videoHeight?: number;
}

export function DetectionOverlay({ cameraId, detections: propDetections, videoWidth, videoHeight }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [scaled, setScaled] = useState<ScaledDetection[]>([]);
  const [debug, setDebug] = useState("");
  const sseDetsRef = useRef<ScaledDetection[]>([]);

  // Rescale whenever props or container size changes
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    const rescale = () => {
      const dw = root.clientWidth;
      const dh = root.clientHeight;
      if (!dw || !dh) {
        setDebug(`overlay ${dw}x${dh}`);
        return;
      }

      if (propDetections && propDetections.length > 0) {
        const sw = videoWidth || 640;
        const sh = videoHeight || 480;
        const now = Date.now();
        const results: ScaledDetection[] = [];
        for (const d of propDetections) {
          if (now - new Date(d.timestamp).getTime() >= STALE_MS) continue;
          const m = mapBbox(d.bbox, sw, sh, dw, dh);
          if (m) results.push({ ...d, ...m });
        }
        setScaled(results);
        setDebug(`${results.length} boxes | overlay ${dw}x${dh} | src ${sw}x${sh}`);
      } else {
        setScaled(sseDetsRef.current);
        setDebug(`${sseDetsRef.current.length} sse | overlay ${dw}x${dh}`);
      }
    };

    rescale();
    const ro = new ResizeObserver(rescale);
    ro.observe(root);
    return () => ro.disconnect();
  }, [cameraId, propDetections, videoWidth, videoHeight]);

  // SSE mode
  useEffect(() => {
    if (propDetections) return;
    const client = new SSEClient();
    client.connect("/api/v1/alerts/stream");
    client.on("detection", (data) => {
      if (data.camera_id !== cameraId) return;
      const raw = data as unknown as LiveDetection;
      const det: ScaledDetection = { ...raw, sx: 0, sy: 0, sw: 0, sh: 0 };
      sseDetsRef.current = [...sseDetsRef.current, det]
        .filter((d) => Date.now() - new Date(d.timestamp).getTime() < STALE_MS)
        .slice(-20);
    });
    return () => { client.disconnect(); };
  }, [cameraId, propDetections]);

  return (
    <div
      ref={rootRef}
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        zIndex: 10,
      }}
    >
      {/* Red test dot ΓÇö proves overlay is visible */}
      <div
        style={{
          position: "absolute",
          top: 6,
          right: 6,
          width: 14,
          height: 14,
          borderRadius: 7,
          background: "#ff0000",
          border: "2px solid white",
          zIndex: 999,
        }}
      />
      {/* Boxes */}
      {scaled.map((det, i) => {
        const color = det.object_type === "person" ? "#34d399" : "#fbbf24";
        const conf = Math.round(det.confidence * 100);
        return (
          <div
            key={`${det.track_id || cameraId}-${i}`}
            style={{
              position: "absolute",
              left: det.sx,
              top: det.sy,
              width: det.sw,
              height: det.sh,
              border: `3px solid ${color}`,
              borderRadius: 4,
              zIndex: 50,
            }}
          >
            <div
              style={{
                position: "absolute",
                top: -22,
                left: 0,
                padding: "2px 8px",
                background: color,
                color: "#000",
                fontSize: 12,
                fontWeight: 700,
                borderRadius: 3,
                whiteSpace: "nowrap",
              }}
            >
              {det.object_type === "person" ? "Person" : "Vehicle"} {conf}%
            </div>
          </div>
        );
      })}
      {/* Debug bar */}
      {debug && (
        <div
          style={{
            position: "absolute",
            bottom: 6,
            left: 6,
            padding: "3px 8px",
            background: "rgba(0,0,0,0.85)",
            color: "#0ff",
            fontSize: 10,
            fontFamily: "monospace",
            borderRadius: 3,
            zIndex: 999,
          }}
        >
          {debug}
        </div>
      )}
    </div>
  );
}
