export type WsMessageHandler = (data: any) => void;
export type WsEventHandler = () => void;

export class ReconnectingWebSocket {
  private url: string;
  private ws: WebSocket | null = null;
  private shouldReconnect = true;
  private reconnectDelayMs = 1000;
  private maxDelayMs = 8000;
  private handler?: WsMessageHandler;
  private onOpen?: WsEventHandler;
  private onClose?: WsEventHandler;
  private pingTimer: number | null = null;

  constructor(url: string, handler?: WsMessageHandler, onOpen?: WsEventHandler, onClose?: WsEventHandler) {
    this.url = url;
    this.handler = handler;
    this.onOpen = onOpen;
    this.onClose = onClose;
    this.connect();
  }

  private connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onmessage = (event) => {
      if (!this.handler) {
        return;
      }
      try {
        this.handler(JSON.parse(event.data));
      } catch {
        this.handler(event.data);
      }
    };

    this.ws.onclose = () => {
      if (this.pingTimer) {
        window.clearInterval(this.pingTimer);
        this.pingTimer = null;
      }
      if (this.onClose) {
        this.onClose();
      }
      if (!this.shouldReconnect) {
        return;
      }
      setTimeout(() => this.connect(), this.reconnectDelayMs);
      this.reconnectDelayMs = Math.min(this.reconnectDelayMs * 2, this.maxDelayMs);
    };

    this.ws.onopen = () => {
      this.reconnectDelayMs = 1000;
      if (this.pingTimer) {
        window.clearInterval(this.pingTimer);
      }
      this.pingTimer = window.setInterval(() => {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send('ping');
        }
      }, 20000);
      if (this.onOpen) {
        this.onOpen();
      }
    };
  }

  public close() {
    this.shouldReconnect = false;
    if (this.pingTimer) {
      window.clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
    if (this.ws) {
      this.ws.close();
    }
  }
}
