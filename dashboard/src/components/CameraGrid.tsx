import { useState, useEffect } from "react";
import { api } from "../services/api";
import { type Camera } from "../types/api";
import { CameraFeed } from "./CameraFeed";
import { WebcamFeed } from "./WebcamFeed";
import { CameraManager } from "./CameraManager";
import { Camera as CameraIcon, Wifi, WifiOff, Monitor, Cctv, Settings } from "lucide-react";

export function CameraGrid() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [webcamEnabled, setWebcamEnabled] = useState(true);
  const [managerOpen, setManagerOpen] = useState(false);

  const load = () => {
    api.getCameras().then(setCameras).catch(() => {});
  };

  useEffect(() => { load(); }, []);

  const totalFeeds = cameras.length + (webcamEnabled ? 1 : 0);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <div className="p-2.5 rounded-xl bg-status-ok/[0.06] border border-status-ok/10">
            <Cctv className="w-5 h-5 text-status-ok" strokeWidth={1.5} />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-text-primary tracking-tight">CCTV Camera Space</h2>
            <p className="text-[11px] text-text-muted mt-0.5 tracking-wide">
              {totalFeeds} {totalFeeds === 1 ? "feed" : "feeds"} active
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Manage Cameras */}
          <button
            onClick={() => setManagerOpen(true)}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl border border-border-subtle bg-surface-2 text-[11px] font-medium tracking-wide text-text-muted hover:text-text-primary hover:border-border-strong transition-all duration-200"
          >
            <Settings className="w-3.5 h-3.5" strokeWidth={1.5} />
            Manage
          </button>

          {/* Toggle webcam */}
          <button
            onClick={() => setWebcamEnabled(!webcamEnabled)}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl border text-[11px] font-medium tracking-wide transition-all duration-200 ${
              webcamEnabled
                ? "bg-accent/[0.06] border-accent/20 text-accent"
                : "bg-surface-2 border-border-subtle text-text-muted hover:text-text-secondary"
            }`}
          >
            <Monitor className="w-3.5 h-3.5" strokeWidth={1.5} />
            Laptop Camera
          </button>
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Laptop webcam */}
        {webcamEnabled && (
          <div className="rounded-2xl border border-border-subtle bg-surface-1 overflow-hidden group hover:border-border-strong transition-all duration-300">
            <div className="relative aspect-video bg-surface-0">
              <WebcamFeed />
            </div>
            <div className="flex items-center justify-between px-5 py-3.5 border-t border-border-subtle">
              <div className="flex items-center gap-2">
                <Monitor className="w-3.5 h-3.5 text-accent" strokeWidth={1.5} />
                <span className="font-mono text-[13px] text-text-primary tracking-wide">Laptop Camera</span>
              </div>
              <div className="flex items-center gap-2">
                <Wifi className="w-3.5 h-3.5 text-status-ok" strokeWidth={1.5} />
                <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-status-ok">
                  Local
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Backend cameras */}
        {cameras.map((cam) => (
          <div
            key={cam.camera_id}
            className="rounded-2xl border border-border-subtle bg-surface-1 overflow-hidden group hover:border-border-strong transition-all duration-300 relative"
          >
            <div className="relative aspect-video bg-surface-0">
              <CameraFeed cameraId={cam.camera_id} />
            </div>
            {/* Hover overlay actions */}
            <div className="absolute top-3 right-3 flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() => setManagerOpen(true)}
                className="p-1.5 rounded-lg bg-black/60 backdrop-blur-sm border border-white/10 text-white/70 hover:text-white hover:bg-black/80 transition-all"
              >
                <Settings className="w-3 h-3" strokeWidth={1.5} />
              </button>
            </div>
            <div className="flex items-center justify-between px-5 py-3.5 border-t border-border-subtle">
              <div className="flex items-center gap-2">
                <CameraIcon className="w-3.5 h-3.5 text-accent" strokeWidth={1.5} />
                <span className="font-mono text-[13px] text-text-primary tracking-wide">{cam.name || cam.camera_id}</span>
              </div>
              <div className="flex items-center gap-2">
                {cam.status === "ok" || cam.status === "online" ? (
                  <Wifi className="w-3.5 h-3.5 text-status-ok" strokeWidth={1.5} />
                ) : (
                  <WifiOff className="w-3.5 h-3.5 text-severity-critical" strokeWidth={1.5} />
                )}
                <span className={`text-[10px] font-semibold uppercase tracking-[0.15em] ${
                  cam.status === "ok" || cam.status === "online" ? "text-status-ok" : "text-severity-critical"
                }`}>
                  {cam.status}
                </span>
              </div>
            </div>
          </div>
        ))}

        {/* No backend cameras + webcam disabled */}
        {cameras.length === 0 && !webcamEnabled && (
          <div className="col-span-2 flex flex-col items-center justify-center py-24 text-text-muted">
            <div className="w-12 h-12 rounded-2xl bg-surface-2 border border-border-subtle flex items-center justify-center mb-4">
              <Cctv className="w-5 h-5 opacity-30" strokeWidth={1.5} />
            </div>
            <p className="text-[13px] font-medium">No cameras active</p>
            <p className="text-[11px] text-text-muted mt-1">Enable laptop camera or register backend cameras</p>
          </div>
        )}

        {/* No backend cameras, webcam is the only feed */}
        {cameras.length === 0 && webcamEnabled && (
          <div className="col-span-2 rounded-2xl border border-border-subtle bg-surface-1 p-8">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-accent/[0.06] border border-accent/10">
                <CameraIcon className="w-4 h-4 text-accent" strokeWidth={1.5} />
              </div>
              <div>
                <p className="text-[13px] font-medium text-text-primary">Additional Cameras</p>
                <p className="text-[11px] text-text-muted">No backend cameras registered yet</p>
              </div>
            </div>
            <button
              onClick={() => setManagerOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl border border-dashed border-accent/30 bg-accent/[0.03] text-accent text-[12px] font-medium hover:bg-accent/[0.06] transition-colors"
            >
              <Settings className="w-3.5 h-3.5" strokeWidth={1.5} />
              Register Camera
            </button>
          </div>
        )}
      </div>

      {/* Camera Manager Modal */}
      <CameraManager open={managerOpen} onClose={() => { setManagerOpen(false); load(); }} />
    </div>
  );
}
