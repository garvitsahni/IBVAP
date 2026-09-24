type SSEEventHandler = (data: Record<string, unknown>) => void;
type ConnectionStateHandler = (connected: boolean) => void;

export class SSEClient {
  private source: EventSource | null = null;
  private handlers: Map<string, SSEEventHandler[]> = new Map();
  private stateHandlers: ConnectionStateHandler[] = [];
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private url = "";
  private closedByUser = false;

  connect(url: string) {
    this.url = url;
    this.closedByUser = false;
    this.open();
  }

  private open() {
    if (this.closedByUser) return;
    this.source?.close();
    const source = new EventSource(this.url);
    this.source = source;

    source.addEventListener("alert_fired", (e) => this.dispatch("alert_fired", JSON.parse(e.data)));
    source.addEventListener("alert_enriched", (e) => this.dispatch("alert_enriched", JSON.parse(e.data)));

    source.onopen = () => {
      this.reconnectDelay = 1000;
      this.emitState(true);
    };
    source.onerror = () => {
      this.emitState(false);
      if (this.closedByUser) return;
      source.close();
      const delay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
      this.reconnectDelay = delay;
      setTimeout(() => this.open(), delay);
    };
  }

  on(event: string, handler: SSEEventHandler) {
    if (!this.handlers.has(event)) this.handlers.set(event, []);
    this.handlers.get(event)!.push(handler);
  }

  onStateChange(handler: ConnectionStateHandler) {
    this.stateHandlers.push(handler);
  }

  private dispatch(event: string, data: Record<string, unknown>) {
    (this.handlers.get(event) || []).forEach((h) => h(data));
  }

  private emitState(connected: boolean) {
    this.stateHandlers.forEach((h) => h(connected));
  }

  disconnect() {
    this.closedByUser = true;
    this.source?.close();
    this.source = null;
    this.emitState(false);
  }
}
