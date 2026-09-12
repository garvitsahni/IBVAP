import { useEffect, useRef } from "react";
import Hls from "hls.js";
import { DetectionOverlay } from "./DetectionOverlay";

export function CameraFeed({ cameraId }: { cameraId: string }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    const url = `/api/v1/streams/${cameraId}.m3u8`;
    let hls: Hls | null = null;
    if (Hls.isSupported()) {
      hls = new Hls();
      hls.loadSource(url);
      hls.attachMedia(video);
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = url;
    }
    return () => { hls?.destroy(); };
  }, [cameraId]);

  return (
    <div className="absolute inset-0">
      <video ref={ref} className="w-full h-full object-cover rounded bg-black" autoPlay muted playsInline />
      <DetectionOverlay cameraId={cameraId} />
    </div>
  );
}
