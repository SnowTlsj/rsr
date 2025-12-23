import { defineStore } from 'pinia';

export type WsStatus = 'closed' | 'connecting' | 'open';

export interface ChannelPoint {
  ts: number;
  value: number;
}

export const useRunStore = defineStore('run', {
  state: () => ({
    runId: null as string | null,
    wsStatus: 'closed' as WsStatus,
    channelBuffers: [[], [], [], [], []] as ChannelPoint[][]
  }),
  actions: {
    setRunId(runId: string | null) {
      this.runId = runId;
    },
    setWsStatus(status: WsStatus) {
      this.wsStatus = status;
    },
    pushTelemetry(values: number[], ts: number) {
      for (let i = 0; i < 5; i += 1) {
        const value = values[i] ?? 0;
        const buffer = this.channelBuffers[i];
        const last = buffer[buffer.length - 1];
        if (last && ts - last.ts < 1000) {
          last.ts = ts;
          last.value = value;
        } else {
          buffer.push({ ts, value });
        }
        if (buffer.length > 600) {
          buffer.splice(0, buffer.length - 600);
        }
      }
    },
    resetBuffers() {
      this.channelBuffers = [[], [], [], [], []];
    }
  }
});
