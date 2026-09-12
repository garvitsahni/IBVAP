import { useEffect, useRef, useState, useCallback } from "react";
import { SSEClient } from "../services/sse";

export function useSSE(url: string) {
  const clientRef = useRef<SSEClient | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const client = new SSEClient();
    clientRef.current = client;
    client.connect(url);
    setConnected(true);
    return () => { client.disconnect(); setConnected(false); };
  }, [url]);

  const on = useCallback((event: string, handler: (data: Record<string, unknown>) => void) => {
    clientRef.current?.on(event, handler);
  }, []);

  return { connected, on };
}
