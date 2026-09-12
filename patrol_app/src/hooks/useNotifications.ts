import { useRef, useCallback } from "react";

export function useNotifications() {
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const requestPermission = useCallback(async () => {
    if ("Notification" in window && Notification.permission === "default") {
      await Notification.requestPermission();
    }
  }, []);

  const notify = useCallback((title: string, body: string) => {
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification(title, { body, icon: "/alert-icon.png" });
    }
    if (!audioRef.current) {
      audioRef.current = new Audio("/alert-sound.mp3");
    }
    audioRef.current.play().catch(() => {});
  }, []);

  return { requestPermission, notify };
}
