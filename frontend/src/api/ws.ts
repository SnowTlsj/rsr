export type WsMessageHandler = (data: any) => void;
export type WsOpenHandler = () => void;
export type WsCloseHandler = (event: CloseEvent) => void;

const normalizeBase = (raw: string) => raw.replace(/\/$/, '');

export const resolveWsBase = (): string => {
  const fromEnv = (import.meta.env.VITE_WS_BASE || '').trim();
  if (fromEnv) {
    return normalizeBase(fromEnv);
  }

  if (typeof window === 'undefined') {
    return 'ws://127.0.0.1:8100';
  }

  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}`;
};

export const buildLiveWsUrl = (runId: string): string => {
  const url = new URL(`${resolveWsBase()}/ws/live`);
  url.searchParams.set('run_id', runId);
  return url.toString();
};

export class ReconnectingWebSocket {
  private url: string;
  private ws: WebSocket | null = null;
  private shouldReconnect = true;
  private reconnectDelayMs = 1000;
  private maxDelayMs = 8000;
  private handler?: WsMessageHandler;
  private onOpen?: WsOpenHandler;
  private onClose?: WsCloseHandler;
  private pingTimer: number | null = null;

  constructor(url: string, handler?: WsMessageHandler, onOpen?: WsOpenHandler, onClose?: WsCloseHandler) {
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

    this.ws.onclose = (event) => {
      if (this.pingTimer) {
        window.clearInterval(this.pingTimer);
        this.pingTimer = null;
      }
      if (event.code === 1008 || event.code === 4401 || event.code === 4403) {
        this.shouldReconnect = false;
      }
      if (this.onClose) {
        this.onClose(event);
      }
      if (!this.shouldReconnect) {
        return;
      }
      window.setTimeout(() => this.connect(), this.reconnectDelayMs);
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
