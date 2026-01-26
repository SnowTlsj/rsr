<template>
  <div class="monitor-container">
    <header class="header">
      <div class="logo-section">
        <img src="@/assets/cau_logo.png" alt="CAU Logo" class="logo" />
      </div>
      <div class="title-section">
        <h1>肉苁蓉播种监测网页端</h1>
      </div>
      <div class="header-actions">
        <button class="action-btn" :class="{ active: isRunning }" @click="toggleRun">
          {{ isRunning ? '停止播种' : '开始播种' }}
        </button>
        <button class="action-btn" @click="manualSync" title="手动同步任务状态">同步</button>
        <button class="action-btn" @click="goHistory">历史数据</button>
      </div>
    </header>

    <!-- 任务状态信息栏 -->
    <div v-if="isRunning" class="task-status-bar">
      <div class="status-item">
        <span class="status-label">任务名称:</span>
        <span class="status-value">{{ currentTaskName || '加载中...' }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">任务ID:</span>
        <span class="status-value task-id">{{ runStore.runId ? runStore.runId.substring(0, 8) + '...' : '-' }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">连接状态:</span>
        <span class="status-value" :class="connectionStatusClass">{{ connectionStatusText }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">设备ID:</span>
        <span class="status-value">{{ machineId }}</span>
      </div>
    </div>

    <main class="main-content">
      <div class="left-panel">
        <h2 class="section-title">播种信息</h2>
        <div class="data-grid">
          <div class="data-row"><label>通道1播种量：</label><div class="value-box">{{ sensorData.channel1.toFixed(1) }}</div><span class="unit">g</span><span class="alarm-light" :class="{ active: alarmData.channel1 }"></span></div>
          <div class="data-row"><label>通道2播种量：</label><div class="value-box">{{ sensorData.channel2.toFixed(1) }}</div><span class="unit">g</span><span class="alarm-light" :class="{ active: alarmData.channel2 }"></span></div>
          <div class="data-row"><label>通道3播种量：</label><div class="value-box">{{ sensorData.channel3.toFixed(1) }}</div><span class="unit">g</span><span class="alarm-light" :class="{ active: alarmData.channel3 }"></span></div>
          <div class="data-row"><label>通道4播种量：</label><div class="value-box">{{ sensorData.channel4.toFixed(1) }}</div><span class="unit">g</span><span class="alarm-light" :class="{ active: alarmData.channel4 }"></span></div>
          <div class="data-row"><label>通道5播种量：</label><div class="value-box">{{ sensorData.channel5.toFixed(1) }}</div><span class="unit">g</span><span class="alarm-light" :class="{ active: alarmData.channel5 }"></span></div>
          <div class="data-row"><label>总播种量：</label><div class="value-box">{{ totalSowing }}</div><span class="unit">g</span></div>
          <div class="data-row"><label>作业里程：</label><div class="value-box">{{ sensorData.mileage.toFixed(1) }}</div><span class="unit">m</span></div>
          <div class="data-row"><label>漏播里程：</label><div class="value-box">{{ sensorData.missedMileage.toFixed(1) }}</div><span class="unit">m</span></div>
          <div class="data-row"><label>作业速度：</label><div class="value-box">{{ sensorData.speed.toFixed(1) }}</div><span class="unit">km/h</span></div>
          <div class="data-row"><label>匀播指数：</label><div class="value-box">{{ uniformityIndex }}</div><span class="unit">g/m</span></div>
        </div>
      </div>

      <div class="right-panel">
        <h2 class="map-title">地图定位</h2>
        <div class="coords-info">
          <span>经度: {{ gpsData.longitude.toFixed(6) }} E</span>
          <span>纬度: {{ gpsData.latitude.toFixed(6) }} N</span>
        </div>
        <div class="map-border">
          <div id="baidu-map-container"></div>
          <button class="map-switch-btn" @click="toggleMapMode">{{ isSatelliteMode ? '切换二维地图' : '切换卫星实景' }}</button>
        </div>
      </div>
    </main>

    <!-- Toast 提示 -->
    <Transition name="toast">
      <div v-if="toast.visible" class="toast" :class="toast.type">
        <div class="toast-content">
          <span class="toast-icon">{{ toast.icon }}</span>
          <span class="toast-message">{{ toast.message }}</span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { reactive, computed, onMounted, watch, ref, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { http } from '@/api/http';
import { ReconnectingWebSocket } from '@/api/ws';
import { useRunStore } from '@/stores/runStore';

const router = useRouter();
const runStore = useRunStore();

const sensorData = reactive({
  channel1: 0, channel2: 0, channel3: 0, channel4: 0, channel5: 0,
  mileage: 0, missedMileage: 0, speed: 0
});

const alarmData = reactive({
  channel1: 0, channel2: 0, channel3: 0, channel4: 0, channel5: 0
});

const totalSowing = computed(() => {
  const sum = sensorData.channel1 + sensorData.channel2 + sensorData.channel3 + sensorData.channel4 + sensorData.channel5;
  return sum.toFixed(1);
});

// 匀播指数计算：五个通道总播种量 / 总里程
const uniformityIndex = computed(() => {
  const total = parseFloat(totalSowing.value);
  const distance = sensorData.mileage;

  if (distance === 0 || total === 0) {
    return '0.0';
  }

  return (total / distance).toFixed(2);
});

const defaultLongitude = parseFloat(import.meta.env.VITE_DEFAULT_LONGITUDE) || 116.3650;
const defaultLatitude = parseFloat(import.meta.env.VITE_DEFAULT_LATITUDE) || 40.0095;
const gpsData = reactive({ longitude: defaultLongitude, latitude: defaultLatitude });
const gpsTrail = ref<Array<{ lon: number; lat: number }>>([]);  // GPS 轨迹点数组

let mapInstance: any = null;
let marker: any = null;
let polyline: any = null;  // 轨迹线
const isSatelliteMode = ref(true);
let wsClient: ReconnectingWebSocket | null = null;
const lastHeartbeatAt = ref<number | null>(null);
let heartbeatTimer: number | null = null;

const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8200/api/v1';
const wsBase = import.meta.env.VITE_WS_BASE || 'ws://localhost:8200';
const machineId = import.meta.env.VITE_MACHINE_ID || 'machine-001';

const isRunning = computed(() => !!runStore.runId);

// 任务状态
const currentTaskName = ref<string>('');

// 连接状态
const connectionStatusText = computed(() => {
  switch (runStore.wsStatus) {
    case 'open': return '已连接';
    case 'connecting': return '连接中...';
    case 'closed': return '未连接';
    default: return '未知';
  }
});

const connectionStatusClass = computed(() => {
  switch (runStore.wsStatus) {
    case 'open': return 'status-connected';
    case 'connecting': return 'status-connecting';
    case 'closed': return 'status-disconnected';
    default: return '';
  }
});

// Toast 提示
const toast = reactive({
  visible: false,
  message: '',
  type: 'info' as 'success' | 'error' | 'warning' | 'info',
  icon: computed(() => {
    switch (toast.type) {
      case 'success': return '✓';
      case 'error': return '✕';
      case 'warning': return '⚠';
      case 'info': return 'ℹ';
      default: return 'ℹ';
    }
  })
});

let toastTimer: number | null = null;

const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info', duration = 3000) => {
  toast.message = message;
  toast.type = type;
  toast.visible = true;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toast.visible = false;
  }, duration);
};

const initMap = () => {
  const BMapGL = (window as any).BMapGL;
  if (!BMapGL) {
    console.warn('Baidu Map GL not available.');
    showToast('地图加载失败，请检查网络连接', 'warning', 5000);
    return;
  }
  try {
    mapInstance = new BMapGL.Map('baidu-map-container');
    const point = new BMapGL.Point(gpsData.longitude, gpsData.latitude);
    mapInstance.centerAndZoom(point, 18);
    mapInstance.enableScrollWheelZoom(true);
    mapInstance.setMapType((window as any).BMAP_EARTH_MAP);
    mapInstance.setTilt(45);
    marker = new BMapGL.Marker(point);
    mapInstance.addOverlay(marker);
  } catch (e) {
    console.error('Map init failed', e);
    showToast('地图初始化失败', 'error');
  }
};

const toggleMapMode = () => {
  if (!mapInstance) return;
  if (isSatelliteMode.value) {
    mapInstance.setMapType((window as any).BMAP_NORMAL_MAP);
    mapInstance.setTilt(0);
  } else {
    mapInstance.setMapType((window as any).BMAP_EARTH_MAP);
    mapInstance.setTilt(45);
  }
  isSatelliteMode.value = !isSatelliteMode.value;
};

watch(() => [gpsData.longitude, gpsData.latitude], ([newLng, newLat]) => {
  if (mapInstance && marker) {
    const BMapGL = (window as any).BMapGL;
    const newPoint = new BMapGL.Point(newLng, newLat);

    // 更新 marker 位置
    marker.setPosition(newPoint);
    mapInstance.panTo(newPoint);

    // 添加到轨迹数组
    gpsTrail.value.push({ lon: newLng, lat: newLat });

    // 绘制轨迹线（累积显示）
    if (gpsTrail.value.length > 1) {
      // 移除旧的轨迹线
      if (polyline) {
        mapInstance.removeOverlay(polyline);
      }

      // 创建新的轨迹线
      const points = gpsTrail.value.map(p => new BMapGL.Point(p.lon, p.lat));
      polyline = new BMapGL.Polyline(points, {
        strokeColor: '#ff0000',
        strokeWeight: 3,
        strokeOpacity: 0.8
      });
      mapInstance.addOverlay(polyline);
    }
  }
});

const goHistory = () => { router.push('/history'); };

const handleMessage = (message: any) => {
  if (!message || typeof message !== 'object') return;
  // 忽略心跳消息
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
    // 更新警报状态
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
  // 如果已经有连接，先关闭
  if (wsClient) {
    wsClient.close();
    wsClient = null;
  }
  const url = `${wsBase}/ws/live?run_id=${runId}`;
  runStore.setWsStatus('connecting');
  wsClient = new ReconnectingWebSocket(
    url,
    handleMessage,
    () => {
      runStore.setWsStatus('open');
      lastHeartbeatAt.value = Date.now();
      showToast('实时数据连接成功', 'success');
    },
    () => {
      runStore.setWsStatus('closed');
    }
  );
};

const closeWebSocket = () => {
  if (wsClient) { wsClient.close(); wsClient = null; }
  runStore.setWsStatus('closed');
  lastHeartbeatAt.value = null;
};

const toggleRun = async () => {
  if (isRunning.value) {
    const runId = runStore.runId;
    closeWebSocket();
    if (runId) {
      try {
        await http.post(`/runs/${runId}/stop`);
        showToast('播种任务已停止', 'success');
      } catch (e) {
        console.error('Stop run failed', e);
        showToast('停止任务失败，请重试', 'error');
      }
    }
    runStore.setRunId(null);
    return;
  }
  try {
    // 调用 start API，后端会自动返回现有活跃任务或创建新任务
    const response = await http.post('/runs/start', { machine_id: machineId });
    const runId = response.data?.run_id;
    if (!runId) {
      showToast('创建任务失败，请重试', 'error');
      return;
    }
    console.log('Started/Joined run:', runId);
    runStore.setRunId(runId);
    runStore.resetBuffers();

    // 清空 GPS 轨迹
    gpsTrail.value = [];
    if (polyline && mapInstance) {
      mapInstance.removeOverlay(polyline);
      polyline = null;
    }

    openWebSocket(runId);
    showToast('播种任务已开始', 'success');
  } catch (e) {
    console.error('Start run failed', e);
    showToast('启动任务失败，请检查网络连接', 'error');
  }
};

// 检测活跃任务
const checkActiveRun = async () => {
  try {
    // 如果 localStorage 中有 runId，先验证它是否仍然活跃
    if (runStore.runId) {
      try {
        const response = await http.get(`/runs/${runStore.runId}`);
        const run = response.data;
        // 如果任务已结束，清除状态
        if (run.ended_at) {
          console.log('Stored run has ended, clearing state');
          runStore.setRunId(null);
          currentTaskName.value = '';
        } else {
          // 任务仍然活跃，直接连接
          console.log('Reconnecting to stored run:', runStore.runId);
          currentTaskName.value = run.run_name;
          openWebSocket(runStore.runId);
          showToast(`已重新连接到任务`, 'success');
          return true;
        }
      } catch (e) {
        // 任务不存在，清除状态
        console.log('Stored run not found, clearing state');
        runStore.setRunId(null);
        currentTaskName.value = '';
      }
    }

    // 查找活跃任务
    const response = await http.get('/runs', { params: { days: 1, machine_id: machineId } });
    const runs = response.data || [];
    const activeRun = runs.find((run: any) => !run.ended_at);
    if (activeRun) {
      console.log('Found active run:', activeRun.run_id);
      runStore.setRunId(activeRun.run_id);
      currentTaskName.value = activeRun.run_name;
      openWebSocket(activeRun.run_id);
      showToast(`已连接到活跃任务: ${activeRun.run_name}`, 'success');
      return true;
    }
  } catch (e) {
    console.error('Check active run failed', e);
  }
  return false;
};

// 手动同步任务状态
const manualSync = async () => {
  console.log('[SYNC] Manual sync triggered');
  showToast('正在同步任务状态...', 'info');

  try {
    // 查找活跃任务
    const response = await http.get('/runs', { params: { days: 1, machine_id: machineId } });
    const runs = response.data || [];
    const activeRun = runs.find((run: any) => !run.ended_at);

    if (activeRun) {
      const activeRunId = activeRun.run_id;
      const activeRunName = activeRun.run_name;

      // 如果当前没有连接，或者连接的任务不同
      if (!runStore.runId || runStore.runId !== activeRunId) {
        console.log(`[SYNC] Switching to active run: ${activeRunId}`);

        // 关闭旧连接
        if (wsClient) {
          closeWebSocket();
        }

        // 连接到新任务
        runStore.setRunId(activeRunId);
        currentTaskName.value = activeRunName;
        openWebSocket(activeRunId);
        showToast(`已同步到任务: ${activeRunName}`, 'success');
      } else {
        // 已经连接到正确的任务
        currentTaskName.value = activeRunName;
        showToast('任务状态已是最新', 'success');
      }
    } else {
      // 没有活跃任务
      if (runStore.runId) {
        console.log('[SYNC] No active run found, clearing state');
        closeWebSocket();
        runStore.setRunId(null);
        currentTaskName.value = '';
      }
      showToast('当前没有活跃任务', 'warning');
    }
  } catch (e) {
    console.error('[SYNC] Manual sync failed', e);
    showToast('同步失败，请检查网络连接', 'error');
  }
};

onMounted(async () => {
  setTimeout(initMap, 500);
  // 自动检测活跃任务
  await checkActiveRun();
  heartbeatTimer = window.setInterval(() => {
    if (runStore.wsStatus === 'open' && lastHeartbeatAt.value) {
      const elapsed = Date.now() - lastHeartbeatAt.value;
      if (elapsed > 15000) {
        runStore.setWsStatus('connecting');
      }
    }
  }, 5000);
});
onBeforeUnmount(() => {
  if (heartbeatTimer) {
    window.clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
  closeWebSocket();
});
</script>


<style scoped>
.monitor-container { font-family: "Microsoft YaHei", sans-serif; width: 100%; max-width: 100%; min-height: 100vh; margin: 0; background-color: #fff; display: flex; flex-direction: column; }
.header { display: flex; align-items: center; padding: 10px 20px; border-bottom: 2px solid #ccc; gap: 20px; }
.logo-section .logo { height: 60px; margin-right: 20px; }
.title-section h1 { font-size: 28px; margin: 0; letter-spacing: 2px; color: #000; font-weight: bold; }
.header-actions { margin-left: auto; display: flex; gap: 10px; }
.action-btn { padding: 8px 16px; border: 1px solid #666; background: #f5f5f5; cursor: pointer; font-size: 14px; border-radius: 4px; transition: all 0.2s; }
.action-btn:hover { background: #e0e0e0; }
.action-btn.active { background: #ff6b6b; color: white; border-color: #ff6b6b; }

/* 任务状态栏 */
.task-status-bar {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 10px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-bottom: 2px solid #5a67d8;
  color: white;
  font-size: 14px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-label {
  font-weight: 500;
  opacity: 0.9;
}

.status-value {
  font-weight: 600;
  background: rgba(255, 255, 255, 0.2);
  padding: 4px 10px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
}

.status-value.task-id {
  font-size: 12px;
  letter-spacing: 0.5px;
}

.status-value.status-connected {
  background: rgba(76, 175, 80, 0.3);
  color: #c8e6c9;
}

.status-value.status-connecting {
  background: rgba(255, 193, 7, 0.3);
  color: #fff9c4;
}

.status-value.status-disconnected {
  background: rgba(244, 67, 54, 0.3);
  color: #ffcdd2;
}

.main-content { display: flex; flex-direction: row; border: 2px dashed #333; margin: 20px; min-height: calc(100vh - 140px); flex: 1; }
.left-panel { flex: 3; padding: 30px 30px 20px 30px; display: flex; flex-direction: column; justify-content: center; }
.section-title { text-align: center; font-size: 24px; font-weight: bold; color: #000; margin: 0 0 30px 0; }
.right-panel { flex: 2; border-left: 2px solid #000; padding: 20px; display: flex; flex-direction: column; }
.data-grid { display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; }
.data-row { display: flex; align-items: center; width: 48%; margin-bottom: 20px; }
.data-row.full-width { width: 100%; }
.data-row label { font-size: 20px; width: 160px; text-align: right; margin-right: 10px; color: #000; font-weight: 500; }
.value-box { background-color: #5b9bd5; border: 1px solid #333; border-radius: 8px; height: 45px; flex-grow: 1; display: flex; align-items: center; justify-content: center; color: white; font-size: 22px; font-weight: bold; box-shadow: 2px 2px 5px rgba(0,0,0,0.2); }
.unit { font-size: 20px; margin-left: 10px; width: 40px; font-style: italic; font-family: "Times New Roman", serif; color: #000; }
.alarm-light { width: 20px; height: 20px; border-radius: 50%; background-color: #4caf50; margin-left: 10px; box-shadow: 0 0 5px rgba(0,0,0,0.3); transition: background-color 0.3s; }
.alarm-light.active { background-color: #f44336; box-shadow: 0 0 10px #f44336; }
.map-title { text-align: center; font-size: 26px; margin-bottom: 10px; margin-top: 0; color: #000; font-weight: bold; }
.coords-info { display: flex; justify-content: space-around; font-size: 20px; margin-bottom: 15px; color: #000; }
.map-border { flex-grow: 1; border: 2px solid #999; position: relative; min-height: 300px; }
#baidu-map-container { width: 100%; height: 100%; background-color: #f0f0f0; }
.map-switch-btn { position: absolute; top: 10px; right: 10px; z-index: 999; padding: 8px 15px; background-color: rgba(255, 255, 255, 0.9); border: 1px solid #999; border-radius: 4px; font-size: 14px; cursor: pointer; box-shadow: 0 2px 5px rgba(0,0,0,0.3); font-weight: bold; }
.map-switch-btn:hover { background-color: #e6e6e6; }

/* Toast 样式 */
.toast {
  position: fixed;
  top: 80px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  padding: 12px 24px;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  font-size: 14px;
  font-weight: 500;
  min-width: 200px;
  max-width: 500px;
}

.toast-content {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #fff;
}

.toast-icon {
  font-size: 18px;
  font-weight: bold;
}

.toast.success {
  background-color: #52c41a;
}

.toast.error {
  background-color: #ff4d4f;
}

.toast.warning {
  background-color: #faad14;
}

.toast.info {
  background-color: #1890ff;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(-20px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-20px);
}

@media (max-width: 900px) {
  .header { flex-direction: column; text-align: center; }
  .logo-section .logo { margin-right: 0; margin-bottom: 5px; height: 40px; }
  .title-section h1 { font-size: 18px; margin-bottom: 5px; }
  .header-actions { margin-left: 0; flex-wrap: wrap; justify-content: center; }
  .main-content { flex-direction: column; margin: 5px; border: 1px dashed #ccc; }
  .left-panel { padding: 10px; border-bottom: 1px solid #eee; }
  .data-grid { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; }
  .data-row { width: 48%; margin-bottom: 0; flex-wrap: wrap; justify-content: center; border: 1px solid #eee; border-radius: 6px; padding: 8px 4px; background-color: rgba(240, 240, 240, 0.5); }
  .data-row.full-width { width: 100%; }
  .single-row { width: 100%; }
  .data-row label { width: 100%; text-align: center; margin-right: 0; font-size: 13px; margin-bottom: 5px; color: #333; }
  .value-box { height: 35px; font-size: 18px; min-width: 60px; }
  .unit { font-size: 12px; margin-left: 4px; width: auto; }
  .right-panel { border-left: none; padding: 10px; height: 400px; }
  .map-title { font-size: 18px; }
  .coords-info { font-size: 12px; flex-direction: column; align-items: center; gap: 6px; }
  .toast { top: 60px; min-width: 150px; max-width: 90%; font-size: 12px; padding: 10px 16px; }
}
</style>
