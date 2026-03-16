<template>
  <div class="monitor-container" :style="containerStyle">
    <header class="header">
      <div class="logo-section">
        <img src="@/assets/cau_logo.png" alt="CAU Logo" class="logo" />
      </div>
      <div class="title-section">
        <h1>肉苁蓉播种监测网页端</h1>
      </div>
      <div class="style-controls">
        <span>主题</span>
        <select v-model="activeTheme" aria-label="背景主题">
          <option value="paper">宣纸浅米</option>
          <option value="landscape">青绿山水</option>
          <option value="pattern">苁蓉纹样</option>
        </select>
        <span>背景透明度</span>
        <input v-model.number="bgOpacity" type="range" min="0" max="1" step="0.05" />
      </div>
      <div class="header-actions">
        <button class="action-btn" :class="{ active: isRunning }" :disabled="isRunActionPending" @click="toggleRun">
          {{ isRunActionPending ? (isRunning ? '停止中...' : '启动中...') : (isRunning ? '停止播种' : '开始播种') }}
        </button>
        <button class="action-btn" :disabled="isSyncPending || isRunActionPending" @click="manualSync" title="手动同步任务状态">
          {{ isSyncPending ? '同步中...' : '同步' }}
        </button>
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
        <span class="status-label">最后心跳:</span>
        <span class="status-value">{{ lastHeartbeatText }}</span>
      </div>
    </div>

    <main class="main-content">
      <div class="left-panel">
        <h2 class="section-title">播种信息</h2>
        <div
          class="cistanche-mascot"
          :style="{ left: `${mascotPos.x}px`, top: `${mascotPos.y}px` }"
          role="button"
          tabindex="0"
          @pointerdown="onMascotPointerDown"
          @click.stop="emitAroma"
          @keydown.enter.prevent="emitAroma"
          @keydown.space.prevent="emitAroma"
        >
          <div class="mascot-stem"></div>
          <div class="mascot-cap"></div>
          <div class="mascot-eye left"></div>
          <div class="mascot-eye right"></div>
          <div class="mascot-smile"></div>
        </div>
        <div class="aroma-layer" aria-hidden="true">
          <span
            v-for="p in aromaParticles"
            :key="p.id"
            class="aroma-particle"
            :style="{ left: `${p.x}px`, top: `${p.y}px`, '--drift': `${p.drift}px`, '--duration': `${p.duration}ms` }"
          />
        </div>
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
import { getAuthToken, http } from '@/api/http';
import { buildLiveWsUrl, ReconnectingWebSocket } from '@/api/ws';
import { useRunStore } from '@/stores/runStore';
import { isAuthError } from '@/utils/httpError';

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
let manualCloseWs = false;
const lastHeartbeatAt = ref<number | null>(null);
let heartbeatTimer: number | null = null;
const isRunActionPending = ref(false);
const isSyncPending = ref(false);
const bgOpacity = ref(0.38);
const activeTheme = ref<'paper' | 'landscape' | 'pattern'>('paper');
const THEME_STORAGE_KEY = 'monitor_theme';
const OPACITY_STORAGE_KEY = 'monitor_theme_opacity';
const themeImageMap: Record<'paper' | 'landscape' | 'pattern', string> = {
  paper: "url('/themes/antique-paper.jpg')",
  landscape: "url('/themes/landscape-ink.jpg')",
  pattern: "url('/themes/cistanche-pattern.webp')"
};
const containerStyle = computed(() => ({
  '--antique-opacity': `${bgOpacity.value}`,
  '--theme-image': themeImageMap[activeTheme.value]
}));
const mascotPos = reactive({ x: 18, y: 76 });
const mascotSize = { w: 86, h: 122 };
const dragState = reactive({
  active: false,
  pointerId: -1,
  offsetX: 0,
  offsetY: 0
});
const aromaParticles = ref<Array<{ id: number; x: number; y: number; drift: number; duration: number }>>([]);
let particleId = 1;

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

const lastHeartbeatText = computed(() => {
  if (!lastHeartbeatAt.value) {
    return '-';
  }
  return new Date(lastHeartbeatAt.value).toLocaleTimeString('zh-CN', { hour12: false });
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

const clampMascotPosition = (nextX: number, nextY: number) => {
  const panel = document.querySelector('.left-panel') as HTMLElement | null;
  if (!panel) {
    mascotPos.x = Math.max(0, nextX);
    mascotPos.y = Math.max(0, nextY);
    return;
  }
  const maxX = Math.max(0, panel.clientWidth - mascotSize.w - 8);
  const maxY = Math.max(0, panel.clientHeight - mascotSize.h - 8);
  mascotPos.x = Math.min(maxX, Math.max(8, nextX));
  mascotPos.y = Math.min(maxY, Math.max(56, nextY));
};

const onMascotPointerDown = (event: PointerEvent) => {
  const panel = document.querySelector('.left-panel') as HTMLElement | null;
  if (!panel) return;
  const panelRect = panel.getBoundingClientRect();
  dragState.active = true;
  dragState.pointerId = event.pointerId;
  dragState.offsetX = event.clientX - panelRect.left - mascotPos.x;
  dragState.offsetY = event.clientY - panelRect.top - mascotPos.y;
};

const onGlobalPointerMove = (event: PointerEvent) => {
  if (!dragState.active || event.pointerId !== dragState.pointerId) return;
  const panel = document.querySelector('.left-panel') as HTMLElement | null;
  if (!panel) return;
  const panelRect = panel.getBoundingClientRect();
  const nextX = event.clientX - panelRect.left - dragState.offsetX;
  const nextY = event.clientY - panelRect.top - dragState.offsetY;
  clampMascotPosition(nextX, nextY);
};

const onGlobalPointerUp = (event: PointerEvent) => {
  if (!dragState.active || event.pointerId !== dragState.pointerId) return;
  dragState.active = false;
  dragState.pointerId = -1;
};

const emitAroma = () => {
  const centerX = mascotPos.x + mascotSize.w / 2;
  const startY = mascotPos.y + 24;
  const batch = Array.from({ length: 9 }).map((_, index) => ({
    id: particleId++,
    x: centerX + (index - 3) * 6,
    y: startY + Math.random() * 10,
    drift: Math.round((Math.random() - 0.5) * 46),
    duration: 1300 + Math.round(Math.random() * 500)
  }));
  aromaParticles.value.push(...batch);
  window.setTimeout(() => {
    const ids = new Set(batch.map((item) => item.id));
    aromaParticles.value = aromaParticles.value.filter((item) => !ids.has(item.id));
  }, 2200);
};

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
    manualCloseWs = true;
    wsClient.close();
    wsClient = null;
    window.setTimeout(() => {
      manualCloseWs = false;
    }, 300);
  }
  const url = buildLiveWsUrl(runId, getAuthToken());
  runStore.setWsStatus('connecting');
  wsClient = new ReconnectingWebSocket(
    url,
    handleMessage,
    () => {
      runStore.setWsStatus('open');
      lastHeartbeatAt.value = Date.now();
      showToast('实时数据连接成功', 'success');
    },
    (event) => {
      if (manualCloseWs || !runStore.runId) {
        runStore.setWsStatus('closed');
        return;
      }
      if (event.code === 1008 || event.code === 4401 || event.code === 4403) {
        runStore.setWsStatus('closed');
        showToast('实时连接鉴权失败，请检查配置中的管理令牌', 'error', 5000);
        return;
      }
      runStore.setWsStatus('connecting');
    }
  );
};

const closeWebSocket = () => {
  manualCloseWs = true;
  if (wsClient) { wsClient.close(); wsClient = null; }
  window.setTimeout(() => {
    manualCloseWs = false;
  }, 300);
  runStore.setWsStatus('closed');
  lastHeartbeatAt.value = null;
};

const toggleRun = async () => {
  if (isRunActionPending.value) {
    return;
  }
  isRunActionPending.value = true;
  if (isRunning.value) {
    const runId = runStore.runId;
    closeWebSocket();
    if (runId) {
      try {
        await http.post(`/runs/${runId}/stop`);
        showToast('播种任务已停止', 'success');
      } catch (e) {
        console.error('Stop run failed', e);
        if (isAuthError(e)) {
          showToast('停止失败：鉴权无效，请检查管理令牌', 'error');
        } else {
          showToast('停止任务失败，请重试', 'error');
        }
      }
    }
    runStore.setRunId(null);
    isRunActionPending.value = false;
    return;
  }
  try {
    // 调用 start API，后端会自动返回现有活跃任务或创建新任务
    const response = await http.post('/runs/start', {});
    const runId = response.data?.run_id;
    currentTaskName.value = response.data?.run_name || '';
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
    if (isAuthError(e)) {
      showToast('启动失败：鉴权无效，请检查管理令牌', 'error');
    } else {
      showToast('启动任务失败，请检查网络连接', 'error');
    }
  } finally {
    isRunActionPending.value = false;
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
    const response = await http.get('/runs', { params: { days: 1 } });
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
  if (isSyncPending.value || isRunActionPending.value) {
    return;
  }
  isSyncPending.value = true;
  console.log('[SYNC] Manual sync triggered');
  showToast('正在同步任务状态...', 'info');

  try {
    // 查找活跃任务
    const response = await http.get('/runs', { params: { days: 1 } });
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
    if (isAuthError(e)) {
      showToast('同步失败：鉴权无效，请检查管理令牌', 'error');
    } else {
      showToast('同步失败，请检查网络连接', 'error');
    }
  } finally {
    isSyncPending.value = false;
  }
};

onMounted(async () => {
  window.addEventListener('pointermove', onGlobalPointerMove);
  window.addEventListener('pointerup', onGlobalPointerUp);
  const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
  if (savedTheme === 'paper' || savedTheme === 'landscape' || savedTheme === 'pattern') {
    activeTheme.value = savedTheme;
  }
  const savedOpacity = localStorage.getItem(OPACITY_STORAGE_KEY);
  if (savedOpacity !== null) {
    const parsed = Number(savedOpacity);
    if (!Number.isNaN(parsed)) {
      bgOpacity.value = Math.max(0, Math.min(1, parsed));
    }
  }
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
  window.removeEventListener('pointermove', onGlobalPointerMove);
  window.removeEventListener('pointerup', onGlobalPointerUp);
  if (toastTimer) {
    window.clearTimeout(toastTimer);
    toastTimer = null;
  }
  if (heartbeatTimer) {
    window.clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
  closeWebSocket();
});

watch(activeTheme, (value) => {
  localStorage.setItem(THEME_STORAGE_KEY, value);
});

watch(bgOpacity, (value) => {
  localStorage.setItem(OPACITY_STORAGE_KEY, String(value));
});
</script>


<style scoped>
.monitor-container {
  font-family: var(--font-main);
  width: 100%;
  max-width: 100%;
  min-height: 100vh;
  margin: 0;
  background-color: var(--c-bg-page);
  display: flex;
  flex-direction: column;
  color: var(--c-text-primary);
  position: relative;
  isolation: isolate;
}
.monitor-container::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: var(--antique-opacity, 0.22);
  background-image:
    var(--theme-image),
    radial-gradient(circle at 15% 18%, rgba(133, 94, 66, 0.28) 0, rgba(133, 94, 66, 0.05) 28%, transparent 45%),
    radial-gradient(circle at 82% 22%, rgba(150, 105, 74, 0.22) 0, rgba(150, 105, 74, 0.04) 30%, transparent 50%),
    radial-gradient(circle at 24% 84%, rgba(123, 84, 58, 0.2) 0, rgba(123, 84, 58, 0.03) 25%, transparent 45%),
    linear-gradient(135deg, rgba(248, 238, 220, 0.72) 0%, rgba(241, 227, 200, 0.38) 55%, rgba(232, 214, 184, 0.32) 100%);
  background-size: cover, auto, auto, auto, auto;
  background-position: center center, center, center, center, center;
  background-repeat: no-repeat, no-repeat, no-repeat, no-repeat, no-repeat;
}
.header { position: relative; z-index: 1; display: flex; align-items: center; padding: 10px 18px; border-bottom: 1px solid var(--c-border); gap: 14px; background: rgba(255, 255, 255, 0.86); box-shadow: var(--shadow-sm); backdrop-filter: blur(2px); }
.logo-section .logo { height: 72px; max-width: 460px; width: auto; margin-right: 8px; object-fit: contain; }
.title-section { flex: 1; min-width: 0; }
.title-section h1 { font-size: 26px; margin: 0; letter-spacing: 0.4px; color: var(--c-text-primary); font-weight: 800; line-height: 1.2; }
.style-controls { display: flex; align-items: center; gap: 8px; padding: 6px 10px; border: 1px solid #b08962; background: linear-gradient(135deg, #ead6bb 0%, #d9bea0 100%); border-radius: 999px; color: #5f4329; font-size: 12px; font-weight: 700; box-shadow: inset 0 -1px 0 rgba(99, 68, 42, 0.2); }
.style-controls select {
  border: 1px solid #b08962;
  border-radius: 999px;
  background: #f4e6d4;
  color: #5f4329;
  font-size: 12px;
  padding: 4px 8px;
  outline: none;
}
.style-controls input { width: 88px; accent-color: #8c5d31; }
.header-actions { margin-left: auto; display: flex; gap: 10px; }
.action-btn { padding: 10px 18px; border: 1px solid #a47a51; background: linear-gradient(140deg, #f2e1cc 0%, #e3c7a6 100%); cursor: pointer; font-size: 16px; border-radius: 999px; transition: all 0.2s; color: #5d3f24; font-weight: 700; white-space: nowrap; box-shadow: inset 0 -1px 0 rgba(100, 68, 38, 0.18); }
.action-btn:hover { background: linear-gradient(140deg, #f6e8d8 0%, #e9d1b4 100%); border-color: #8f653f; }
.action-btn.active { background: #dc2626; color: white; border-color: #dc2626; }
.action-btn:disabled { opacity: 0.6; cursor: not-allowed; }

/* 任务状态栏 */
.task-status-bar {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  background: linear-gradient(90deg, #1e3a8a 0%, #1d4ed8 100%);
  border-bottom: 1px solid #1e3a8a;
  color: white;
  font-size: 14px;
  flex-wrap: wrap;
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
  background: rgba(255, 255, 255, 0.16);
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

.main-content { position: relative; z-index: 1; display: grid; grid-template-columns: 1.4fr 1fr; border: 1px solid rgba(157, 176, 200, 0.7); margin: 12px; min-height: calc(100vh - 110px); flex: 1; background: rgba(255, 255, 255, 0.72); box-shadow: var(--shadow-md); border-radius: 14px; overflow: hidden; backdrop-filter: blur(1px); }
.left-panel { position: relative; padding: 16px 14px 12px; display: flex; flex-direction: column; min-height: 0; }
.section-title { text-align: left; font-size: 24px; font-weight: 800; color: var(--c-text-primary); margin: 0 0 12px 0; }
.cistanche-mascot {
  position: absolute;
  left: 20px;
  bottom: 20px;
  width: 86px;
  height: 122px;
  cursor: grab;
  opacity: 0.82;
  z-index: 3;
  touch-action: none;
  user-select: none;
}
.cistanche-mascot:active { cursor: grabbing; }
.mascot-stem {
  position: absolute;
  left: 16px;
  bottom: 0;
  width: 56px;
  height: 96px;
  border-radius: 28px 28px 18px 18px;
  background: linear-gradient(180deg, #d18d56 0%, #af6d3f 68%, #93552f 100%);
  box-shadow: inset 0 -6px 0 rgba(0, 0, 0, 0.08), inset 8px 0 0 rgba(255, 255, 255, 0.15);
}
.mascot-cap {
  position: absolute;
  left: 8px;
  bottom: 78px;
  width: 72px;
  height: 34px;
  border-radius: 32px;
  background: linear-gradient(180deg, #e3a56a 0%, #ba7a49 100%);
  box-shadow: inset 0 -4px 0 rgba(0, 0, 0, 0.08);
}
.mascot-eye {
  position: absolute;
  bottom: 42px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3d2a1d;
}
.mascot-eye.left { left: 34px; }
.mascot-eye.right { left: 48px; }
.mascot-smile {
  position: absolute;
  left: 36px;
  bottom: 30px;
  width: 12px;
  height: 8px;
  border-bottom: 2px solid #5a3b26;
  border-radius: 0 0 10px 10px;
}
.aroma-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 2;
}
.aroma-particle {
  position: absolute;
  width: 12px;
  height: 18px;
  background: linear-gradient(160deg, rgba(255, 237, 181, 0.95) 0%, rgba(236, 191, 113, 0.9) 45%, rgba(196, 142, 73, 0.82) 100%);
  border-radius: 82% 22% 70% 30% / 70% 36% 64% 30%;
  transform-origin: 50% 100%;
  box-shadow: inset -1px -1px 0 rgba(123, 84, 43, 0.22), 0 1px 2px rgba(121, 88, 52, 0.24);
  animation: aroma-rise var(--duration) ease-out forwards;
}
@keyframes aroma-rise {
  0% { transform: translate(0, 0) rotate(-8deg) scale(0.72); opacity: 0.95; }
  35% { opacity: 0.8; }
  100% { transform: translate(var(--drift), -76px) rotate(26deg) scale(1.1); opacity: 0; }
}
.right-panel { border-left: 1px solid rgba(157, 176, 200, 0.7); padding: 14px; display: flex; flex-direction: column; background: rgba(248, 251, 255, 0.75); }
.data-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); grid-template-rows: repeat(5, minmax(0, 1fr)); gap: 14px; flex: 1; min-height: 0; }
.data-row { display: grid; grid-template-columns: 138px 1fr auto auto; align-items: center; width: 100%; margin-bottom: 0; padding: 10px 12px; border: 1px solid rgba(226, 232, 240, 0.85); border-radius: 10px; background: rgba(255, 255, 255, 0.82); height: 100%; min-height: 78px; }
.data-row.full-width { width: 100%; }
.data-row label { font-size: 15px; width: auto; text-align: left; margin-right: 0; color: #334155; font-weight: 700; }
.value-box { background: linear-gradient(180deg, #2563eb 0%, #1d4ed8 100%); border: 1px solid #1e40af; border-radius: 9px; height: 40px; display: flex; align-items: center; justify-content: center; color: white; font-size: 23px; font-weight: 800; letter-spacing: 0.2px; box-shadow: inset 0 -2px 0 rgba(0,0,0,0.15); }
.unit { font-size: 13px; margin-left: 8px; width: 38px; font-style: normal; font-family: var(--font-main); color: #475569; font-weight: 700; text-align: center; }
.alarm-light { width: 16px; height: 16px; border-radius: 50%; background-color: var(--c-success); margin-left: 8px; box-shadow: 0 0 0 3px rgba(46,125,50,0.12); transition: background-color 0.3s; }
.alarm-light.active { background-color: var(--c-danger); box-shadow: 0 0 10px var(--c-danger); }
.map-title { text-align: left; font-size: 26px; margin-bottom: 8px; margin-top: 0; color: var(--c-text-primary); font-weight: 800; }
.coords-info { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 16px; margin-bottom: 8px; color: #334155; background: rgba(255, 255, 255, 0.85); border: 1px solid rgba(215, 227, 240, 0.9); border-radius: 10px; padding: 8px 10px; white-space: nowrap; }
.map-border { flex-grow: 1; border: 1px solid var(--c-border-strong); position: relative; min-height: 300px; border-radius: 10px; overflow: hidden; box-shadow: var(--shadow-sm); height: min(68vh, 760px); }
#baidu-map-container { width: 100%; height: 100%; background-color: #f0f0f0; }
.map-switch-btn { position: absolute; top: 10px; right: 10px; z-index: 999; padding: 8px 12px; background-color: rgba(255, 255, 255, 0.96); border: 1px solid var(--c-border); border-radius: 999px; font-size: 13px; cursor: pointer; box-shadow: var(--shadow-sm); font-weight: 700; color: var(--c-text-primary); }
.map-switch-btn:hover { background-color: #eef4fb; }

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
  .header { flex-direction: column; text-align: center; gap: 10px; }
  .logo-section .logo { margin-right: 0; margin-bottom: 5px; height: 40px; }
  .title-section h1 { font-size: 26px; margin-bottom: 5px; }
  .style-controls { order: 3; width: 100%; justify-content: center; }
  .header-actions { margin-left: 0; flex-wrap: wrap; justify-content: center; }
  .action-btn { font-size: 13px; padding: 8px 12px; }
  .main-content { grid-template-columns: 1fr; margin: 8px; min-height: calc(100vh - 92px); }
  .left-panel { padding: 10px; border-bottom: 1px solid #e7edf4; }
  .section-title { font-size: 22px; }
  .data-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); grid-template-rows: repeat(5, minmax(0, 1fr)); gap: 10px; }
  .data-row { grid-template-columns: 1fr; grid-template-areas: 'label' 'value'; gap: 6px; padding: 8px; min-height: 92px; }
  .data-row label { grid-area: label; font-size: 13px; text-align: center; }
  .value-box { grid-area: value; height: 34px; font-size: 17px; }
  .unit { position: absolute; right: 8px; bottom: 8px; font-size: 11px; }
  .alarm-light { position: absolute; right: 8px; top: 8px; width: 12px; height: 12px; margin-left: 0; }
  .data-row { position: relative; }
  .cistanche-mascot { display: none; }
  .aroma-layer { display: none; }
  .right-panel { border-left: none; padding: 10px; min-height: 420px; }
  .map-title { font-size: 20px; }
  .coords-info { font-size: 13px; flex-direction: column; align-items: flex-start; white-space: normal; }
  .map-switch-btn { font-size: 12px; }
  .toast { top: 60px; min-width: 150px; max-width: 90%; font-size: 12px; padding: 10px 16px; }
}
</style>
