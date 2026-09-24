import { useCallback, useRef } from "react";

// Real alert feedback with no external assets: a short two-tone beep via
// Web Audio (LAN-only rule — no /alert-sound.mp3 to ship) plus vibration.
export function useNotifications() {
  const ctxRef = useRef<AudioContext | null>(null);

  const beep = useCallback(() => {
    try {
      const Ctx: typeof AudioContext | undefined =
        window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctx) return;
      if (!ctxRef.current) ctxRef.current = new Ctx();
      const ctx = ctxRef.current;
      if (ctx.state === "suspended") void ctx.resume();
      const t0 = ctx.currentTime;
      [880, 660].forEach((freq, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "square";
        osc.frequency.value = freq;
        const start = t0 + i * 0.16;
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(0.15, start + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.14);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(start);
        osc.stop(start + 0.15);
      });
    } catch {
      // Audio unavailable (blocked/unsupported) — vibration still fires below.
    }
  }, []);

  const vibrate = useCallback(() => {
    try {
      navigator.vibrate?.([120, 60, 120]);
    } catch {
      // Vibration unsupported (desktop / iOS Safari).
    }
  }, []);

  const notify = useCallback((title: string, body: string) => {
    beep();
    vibrate();
    if ("Notification" in window && Notification.permission === "granted") {
      try {
        new Notification(title, { body, icon: "/favicon.svg" });
      } catch {
        // Some browsers require a service worker for notifications.
      }
    }
  }, [beep, vibrate]);

  const requestPermission = useCallback(async () => {
    if (!("Notification" in window)) return false;
    if (Notification.permission === "default") {
      const perm = await Notification.requestPermission();
      return perm === "granted";
    }
    return Notification.permission === "granted";
  }, []);

  return { requestPermission, notify };
}
