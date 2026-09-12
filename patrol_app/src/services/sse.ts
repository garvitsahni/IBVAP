type SSEEventHandler = (data: Record<string, unknown>) => void;

export class SSEClient {
  private source: EventSource | null = null;
  private handlers: Map<string, SSEEventHandler[]> = new Map();
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;

  connect(url: string) {
    this.source = new EventSource(url);
    this.source.addEventListener("alert_fired", (e) => this.dispatch("alert_fired", JSON.parse(e.data)));
    this.source.addEventListener("alert_enriched", (e) => this.dispatch("alert_enriched", JSON.parse(e.data)));
    this.source.onerror = () => {
      this.source?.close();
      setTimeout(() => this.connect(url), Math.min(this.reconnectDelay * 2, this.maxReconnectDelay));
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
    };
    this.source.onopen = () => { this.reconnectDelay = 1000; };
  }

  on(event: string, handler: SSEEventHandler) {
    if (!this.handlers.has(event)) this.handlers.set(event, []);
    this.handlers.get(event)!.push(handler);
  }

  private dispatch(event: string, data: Record<string, unknown>) {
    (this.handlers.get(event) || []).forEach((h) => h(data));
  }

  disconnect() { this.source?.close(); }
}
