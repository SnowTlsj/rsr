import { computed, onBeforeUnmount, reactive, ref } from 'vue';
import { http } from '@/api/http';
import { buildLiveWsUrl, ReconnectingWebSocket } from '@/api/ws';
import { useRunStore } from '@/stores/runStore';
import { extractErrorMessage, isAuthError } from '@/utils/httpError';

interface ToastApi {
  success: (message: string, duration?: number) => void;
  error: (message: string, duration?: number) => void;
  warning: (message: string, duration?: number) => void;
  info: (message: string, duration?: number) => void;
}

interface UseMonitorRealtimeOptions {
  toast: ToastApi;
  defaultLongitude: number;
  defaultLatitude: number;
  onRunStarted?: () => void;
  onRunStopped?: () => void;
}

export function useMonitorRealtime(options: UseMonitorRealtimeOptions) {
  const runStore = useRunStore();
  const sensorData = reactive({
    channel1: 0,
    channel2: 0,
    channel3: 0,
    channel4: 0,
    channel5: 0,
    mileage: 0,
    missedMileage: 0,
    speed: 0
  });
  const alarmData = reactive({
    channel1: 0,
    channel2: 0,
    channel3: 0,
    channel4: 0,
    channel5: 0
  });
  const gpsData = reactive({
    longitude: options.defaultLongitude,
    latitude: options.defaultLatitude
  });
  const currentTaskName = ref('');
  const lastHeartbeatAt = ref<number | null>(null);
  const isRunActionPending = ref(false);
  const isSyncPending = ref(false);

  let wsClient: ReconnectingWebSocket | null = null;
  let manualCloseWs = false;
  let heartbeatTimer: number | null = null;

  const resolveRequestErrorMessage = (requestError: unknown, fallback: string) => {
    if (isAuthError(requestError)) {
      return '管理会话已失效，请重新登录';
    }
    return extractErrorMessage(requestError, fallback);
  };

  const isRunning = computed(() => !!runStore.runId);
  const totalSowing = computed(() => {
    const sum = sensorData.channel1 + sensorData.channel2 + sensorData.channel3 + sensorData.channel4 + sensorData.channel5;
    return sum.toFixed(1);
  });
  const uniformityIndex = computed(() => {
    const total = parseFloat(totalSowing.value);
    const distance = sensorData.mileage;
    if (distance === 0 || total === 0) {
      return '0.0';
    }
    return (total / distance).toFixed(2);
  });
  const connectionStatusText = computed(() => {
    switch (runStore.wsStatus) {
      case 'open':
        return '已连接';
      case 'connecting':
        return '连接中...';
      case 'closed':
        return '未连接';
      default:
        return '未知';
    }
  });
  const connectionStatusClass = computed(() => {
    switch (runStore.wsStatus) {
      case 'open':
        return 'status-connected';
      case 'connecting':
        return 'status-connecting';
      case 'closed':
        return 'status-disconnected';
      default:
        return '';
    }
  });
  const lastHeartbeatText = computed(() => {
    if (!lastHeartbeatAt.value) {
      return '-';
    }
    return new Date(lastHeartbeatAt.value).toLocaleTimeString('zh-CN', { hour12: false });
  });

  const handleMessage = (message: any) => {
    if (!message || typeof message !== 'object') return;

    if (message.type === 'heartbeat') {
      lastHeartbeatAt.value = Date.now();
      if (runStore.wsStatus !== 'open') {
        runStore.setWsStatus('open');
      }
      return;
    }

    if (message.type === 'telemetry') {
      const data = message.data || {};
      const channels = data.seed_channels_g || [];
      sensorData.channel1 = Number(channels[0] ?? sensorData.channel1);
      sensorData.channel2 = Number(channels[1] ?? sensorData.channel2);
      sensorData.channel3 = Number(channels[2] ?? sensorData.channel3);
      sensorData.channel4 = Number(channels[3] ?? sensorData.channel4);
      sensorData.channel5 = Number(channels[4] ?? sensorData.channel5);
      sensorData.mileage = Number(data.distance_m ?? sensorData.mileage);
      sensorData.missedMileage = Number(data.leak_distance_m ?? sensorData.missedMileage);
      sensorData.speed = Number(data.speed_kmh ?? sensorData.speed);
      const alarms = data.alarm_channels || [];
      alarmData.channel1 = Number(alarms[0] ?? 0);
      alarmData.channel2 = Number(alarms[1] ?? 0);
      alarmData.channel3 = Number(alarms[2] ?? 0);
      alarmData.channel4 = Number(alarms[3] ?? 0);
      alarmData.channel5 = Number(alarms[4] ?? 0);
      const ts = data.ts ? new Date(data.ts).getTime() : Date.now();
      runStore.pushTelemetry(channels, ts);
    }

    if (message.type === 'gps') {
      const data = message.data || {};
      gpsData.longitude = Number(data.lon ?? gpsData.longitude);
      gpsData.latitude = Number(data.lat ?? gpsData.latitude);
    }
  };

  const openWebSocket = (runId: string) => {
    if (wsClient) {
      manualCloseWs = true;
      wsClient.close();
      wsClient = null;
      window.setTimeout(() => {
        manualCloseWs = false;
      }, 300);
    }

    const url = buildLiveWsUrl(runId);
    runStore.setWsStatus('connecting');
    wsClient = new ReconnectingWebSocket(
      url,
      handleMessage,
      () => {
        runStore.setWsStatus('open');
        lastHeartbeatAt.value = Date.now();
        options.toast.success('实时数据连接成功');
      },
      (event) => {
        if (manualCloseWs || !runStore.runId) {
          runStore.setWsStatus('closed');
          return;
        }
        if (event.code === 1008 || event.code === 4401 || event.code === 4403) {
          runStore.setWsStatus('closed');
          options.toast.error('实时连接鉴权失败，请重新建立管理会话', 5000);
          return;
        }
        runStore.setWsStatus('connecting');
      }
    );
  };

  const closeWebSocket = () => {
    manualCloseWs = true;
    if (wsClient) {
      wsClient.close();
      wsClient = null;
    }
    window.setTimeout(() => {
      manualCloseWs = false;
    }, 300);
    runStore.setWsStatus('closed');
    lastHeartbeatAt.value = null;
  };

  const toggleRun = async () => {
    if (isRunActionPending.value) return;
    isRunActionPending.value = true;

    if (isRunning.value) {
      const runId = runStore.runId;
      closeWebSocket();
      if (runId) {
        try {
          await http.post(`/runs/${runId}/stop`);
          options.toast.success('播种任务已停止');
        } catch (requestError) {
          options.toast.error(resolveRequestErrorMessage(requestError, '停止任务失败，请重试'));
        }
      }
      runStore.setRunId(null);
      currentTaskName.value = '';
      options.onRunStopped?.();
      isRunActionPending.value = false;
      return;
    }

    try {
      const response = await http.post('/runs/start', {});
      const runId = response.data?.run_id;
      currentTaskName.value = response.data?.run_name || '';
      if (!runId) {
        options.toast.error('创建任务失败，请重试');
        return;
      }

      runStore.setRunId(runId);
      runStore.resetBuffers();
      options.onRunStarted?.();
      openWebSocket(runId);
      options.toast.success('播种任务已开始');
    } catch (requestError) {
      options.toast.error(resolveRequestErrorMessage(requestError, '启动任务失败，请检查网络连接'));
    } finally {
      isRunActionPending.value = false;
    }
  };

  const checkActiveRun = async () => {
    try {
      if (runStore.runId) {
        try {
          const response = await http.get(`/runs/${runStore.runId}`);
          const run = response.data;
          if (run.ended_at) {
            runStore.setRunId(null);
            currentTaskName.value = '';
          } else {
            currentTaskName.value = run.run_name;
            openWebSocket(runStore.runId);
            options.toast.success('已重新连接到任务');
            return true;
          }
        } catch {
          runStore.setRunId(null);
          currentTaskName.value = '';
        }
      }

      const response = await http.get('/runs', { params: { days: 1 } });
      const runs = response.data || [];
      const activeRun = runs.find((run: any) => !run.ended_at);
      if (activeRun) {
        runStore.setRunId(activeRun.run_id);
        currentTaskName.value = activeRun.run_name;
        openWebSocket(activeRun.run_id);
        options.toast.success(`已连接到活跃任务: ${activeRun.run_name}`);
        return true;
      }
    } catch {
      // ignore background sync failure here
    }
    return false;
  };

  const manualSync = async () => {
    if (isSyncPending.value || isRunActionPending.value) return;
    isSyncPending.value = true;
    options.toast.info('正在同步任务状态...');

    try {
      const response = await http.get('/runs', { params: { days: 1 } });
      const runs = response.data || [];
      const activeRun = runs.find((run: any) => !run.ended_at);

      if (activeRun) {
        const activeRunId = activeRun.run_id;
        const activeRunName = activeRun.run_name;
        if (!runStore.runId || runStore.runId !== activeRunId) {
          if (wsClient) {
            closeWebSocket();
          }
          runStore.setRunId(activeRunId);
          currentTaskName.value = activeRunName;
          options.onRunStarted?.();
          openWebSocket(activeRunId);
          options.toast.success(`已同步到任务: ${activeRunName}`);
        } else {
          currentTaskName.value = activeRunName;
          options.toast.success('任务状态已是最新');
        }
      } else {
        if (runStore.runId) {
          closeWebSocket();
          runStore.setRunId(null);
          currentTaskName.value = '';
          options.onRunStopped?.();
        }
        options.toast.warning('当前没有活跃任务');
      }
    } catch (requestError) {
      options.toast.error(resolveRequestErrorMessage(requestError, '同步失败，请检查网络连接'));
    } finally {
      isSyncPending.value = false;
    }
  };

  const startHeartbeatMonitor = () => {
    heartbeatTimer = window.setInterval(() => {
      if (runStore.wsStatus === 'open' && lastHeartbeatAt.value) {
        const elapsed = Date.now() - lastHeartbeatAt.value;
        if (elapsed > 15000) {
          runStore.setWsStatus('connecting');
        }
      }
    }, 5000);
  };

  const dispose = () => {
    if (heartbeatTimer) {
      window.clearInterval(heartbeatTimer);
      heartbeatTimer = null;
    }
    closeWebSocket();
  };

  onBeforeUnmount(dispose);

  return {
    runStore,
    sensorData,
    alarmData,
    gpsData,
    currentTaskName,
    isRunning,
    isRunActionPending,
    isSyncPending,
    totalSowing,
    uniformityIndex,
    connectionStatusText,
    connectionStatusClass,
    lastHeartbeatText,
    toggleRun,
    manualSync,
    checkActiveRun,
    startHeartbeatMonitor,
    dispose
  };
}
