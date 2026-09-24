import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Bell, BellOff } from "lucide-react";
import { useSSE } from "@/hooks/useSSE";
import { mapApiAlert, type FeedAlert } from "@/lib/alerts";
import type { Alert as ApiAlert } from "@/types/api";

const MUTE_KEY = "ibvap.alerts.muted";
const BANNER_MS = 5000;
const BEEP_MIN_GAP_MS = 1000;

function readMuted(): boolean {
  try { return localStorage.getItem(MUTE_KEY) === "1"; } catch { return false; }
}

function playTwoToneBeep() {
  if (typeof window === "undefined") return;
  if (document.visibilityState !== "visible") return;
  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, now);
    osc.frequency.setValueAtTime(1174.7, now + 0.12);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.2, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.4);
    osc.onended = () => ctx.close().catch(() => {});
  } catch {
    // Audio may be blocked by browser policy — never break the page for a beep.
  }
}

export function AlertBanner() {
  const navigate = useNavigate();
  const location = useLocation();
  const { on } = useSSE("/api/v1/alerts/stream");
  const [banner, setBanner] = useState<FeedAlert | null>(null);
  const [muted, setMuted] = useState(readMuted);
  const lastBeep = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dismiss = useCallback(() => {
    setBanner(null);
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
  }, []);

  const show = useCallback((alert: FeedAlert) => {
    setBanner(alert);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(dismiss, BANNER_MS);
  }, [dismiss]);

  useEffect(() => {
    on("alert_fired", (data) => {
      const mapped = mapApiAlert(data as unknown as ApiAlert);
      const now = Date.now();
      if (!readMuted() && now - lastBeep.current >= BEEP_MIN_GAP_MS) {
        lastBeep.current = now;
        playTwoToneBeep();
      }
      show(mapped);
    });
    // Cleanup: SSE client disconnects via useSSE unmount; clear local timer.
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [on, show]);

  const toggleMute = () => {
    const next = !muted;
    setMuted(next);
    try { localStorage.setItem(MUTE_KEY, next ? "1" : "0"); } catch { /* ignore */ }
  };

  const handleClick = () => {
    if (!banner) return;
    dismiss();
    navigate("/alerts", { state: { selectAlertId: banner.id }, replace: true });
  };

  if (!banner) {
    return (
      <button
        onClick={toggleMute}
        title={muted ? "Alert sound muted" : "Alert sound on"}
        className="fixed bottom-4 right-4 z-50 rounded-full border border-border bg-surface p-2 text-text-muted shadow-lg hover:text-text"
      >
        {muted ? <BellOff size={16} /> : <Bell size={16} />}
      </button>
    );
  }

  return (
    <>
      {/* Banner */}
      <div
        className="fixed left-1/2 top-4 z-50 w-[min(480px,92vw)] -translate-x-1/2 cursor-pointer rounded-lg border border-severity-critical/40 bg-surface px-4 py-3 shadow-xl"
        onClick={handleClick}
        role="alert"
      >
        <div className="flex items-center gap-3">
          <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-severity-critical" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-semibold text-text-primary">
              {banner.type} · {banner.cameraId}
            </p>
            <p className="truncate text-[11px] text-text-muted">
              {banner.reasonDetail ?? `score ${banner.threatScore.toFixed(2)}`} — click to view
            </p>
          </div>
          <span className="shrink-0 rounded bg-severity-critical/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-severity-critical">
            {banner.severity}
          </span>
        </div>
      </div>

      {/* Mute toggle stays available while a banner shows */}
      <button
        onClick={toggleMute}
        title={muted ? "Alert sound muted" : "Alert sound on"}
        className="fixed bottom-4 right-4 z-50 rounded-full border border-border bg-surface p-2 text-text-muted shadow-lg hover:text-text"
      >
        {muted ? <BellOff size={16} /> : <Bell size={16} />}
      </button>
    </>
  );
}
