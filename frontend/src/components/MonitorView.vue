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
        <button class="action-btn" @click="toggleRun">{{ isRunning ? '停止播种' : '开始播种' }}</button>
        <button class="action-btn" @click="toggleTrend">趋势表格</button>
        <button class="action-btn" @click="goHistory">历史数据</button>
      </div>
    </header>

    <main class="main-content">
      <!-- 左侧数据面板 -->
      <div class="left-panel">
        <div class="data-grid">
          <template v-if="!showTrendTable">
            <div class="data-row"><label>通道1播种量：</label><div class="value-box">{{ sensorData.channel1.toFixed(1) }}</div><span class="unit">g</span></div>
            <div class="data-row"><label>通道2播种量：</label><div class="value-box">{{ sensorData.channel2.toFixed(1) }}</div><span class="unit">g</span></div>
            <div class="data-row"><label>通道3播种量：</label><div class="value-box">{{ sensorData.channel3.toFixed(1) }}</div><span class="unit">g</span></div>
            <div class="data-row"><label>通道4播种量：</label><div class="value-box">{{ sensorData.channel4.toFixed(1) }}</div><span class="unit">g</span></div>
            <div class="data-row"><label>通道5播种量：</label><div class="value-box">{{ sensorData.channel5.toFixed(1) }}</div><span class="unit">g</span></div>
          </template>
          <template v-else>
            <div class="data-row full-width">
              <ChannelTrendTable
                :channels="[sensorData.channel1, sensorData.channel2, sensorData.channel3, sensorData.channel4, sensorData.channel5]"
                :buffers="runStore.channelBuffers"
              />
            </div>
          </template>

          <div class="data-row"><label>总播种量：</label><div class="value-box">{{ totalSowing }}</div><span class="unit">g</span></div>
          <div class="data-row"><label>作业里程：</label><div class="value-box">{{ sensorData.mileage.toFixed(1) }}</div><span class="unit">m</span></div>
          <div class="data-row"><label>漏播里程：</label><div class="value-box">{{ sensorData.missedMileage.toFixed(1) }}</div><span class="unit">m</span></div>
          <div class="data-row single-row"><label>作业速度：</label><div class="value-box">{{ sensorData.speed.toFixed(1) }}</div><span class="unit">km/h</span></div>
        </div>

        <div class="indicators-area">
          <div class="indicator-item">
            <span>堵塞指示灯</span>
            <svg class="bulb-icon" :class="{ active: status.blocked }" viewBox="0 0 24 24"><path fill="currentColor" d="M9,21c0,0.55 0.45,1 1,1h4c0.55,0 1,-0.45 1,-1v-1H9V21z M12,2C8.13,2 5,5.13 5,9c0,2.38 1.19,4.47 3,5.74V17c0,0.55 0.45,1 1,1h6c0.55,0 1,-0.45 1,-1v-2.26c1.81,-1.27 3,-3.36 3,-5.74C19,5.13 15.87,2 12,2z"/></svg>
          </div>
          <div class="indicator-item">
            <span>缺种指示灯</span>
            <svg class="bulb-icon" :class="{ active: status.shortage }" viewBox="0 0 24 24"><path fill="currentColor" d="M9,21c0,0.55 0.45,1 1,1h4c0.55,0 1,-0.45 1,-1v-1H9V21z M12,2C8.13,2 5,5.13 5,9c0,2.38 1.19,4.47 3,5.74V17c0,0.55 0.45,1 1,1h6c0.55,0 1,-0.45 1,-1v-2.26c1.81,-1.27 3,-3.36 3,-5.74C19,5.13 15.87,2 12,2z"/></svg>
          </div>
        </div>
      </div>

      <!-- 右侧地图 -->
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
  </div>
</template>

<script setup lang="ts">
import { reactive, computed, onMounted, watch, ref, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import ChannelTrendTable from '@/components/ChannelTrendTable.vue';
import { http } from '@/api/http';
import { ReconnectingWebSocket } from '@/api/ws';
import { useRunStore } from '@/stores/runStore';

const router = useRouter();
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

const totalSowing = computed(() => {
  const sum = Number(sensorData.channel1) +
              Number(sensorData.channel2) +
              Number(sensorData.channel3) +
              Number(sensorData.channel4) +
              Number(sensorData.channel5);
  return sum.toFixed(1);
});

const gpsData = reactive({
  longitude: 116.3650,
  latitude: 40.0095
});

const status = reactive({ blocked: false, shortage: false });

let mapInstance: any = null;
let marker: any = null;
const isSatelliteMode = ref(true);
const showTrendTable = ref(false);

let wsClient: ReconnectingWebSocket | null = null;

const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';
const wsBase = import.meta.env.VITE_WS_BASE || apiBase.replace('http', 'ws').replace('/api/v1', '');
const machineId = import.meta.env.VITE_MACHINE_ID || '';

const isRunning = computed(() => !!runStore.runId);

const initMap = () => {
  const BMapGL = window.BMapGL;
  if (!BMapGL) {
    console.warn('Baidu Map GL not available.');
    return;
  }
  try {
    mapInstance = new BMapGL.Map('baidu-map-container');
    const point = new BMapGL.Point(gpsData.longitude, gpsData.latitude);
    mapInstance.centerAndZoom(point, 18);
    mapInstance.enableScrollWheelZoom(true);
    mapInstance.setMapType(BMAP_EARTH_MAP);
    mapInstance.setTilt(45);
    marker = new BMapGL.Marker(point);
    mapInstance.addOverlay(marker);
  } catch (e) {
    console.error('Map init failed', e);
  }
};

const toggleMapMode = () => {
  if (!mapInstance) return;
  if (isSatelliteMode.value) {
    mapInstance.setMapType(BMAP_NORMAL_MAP);
    mapInstance.setTilt(0);
  } else {
    mapInstance.setMapType(BMAP_EARTH_MAP);
    mapInstance.setTilt(45);
  }
  isSatelliteMode.value = !isSatelliteMode.value;
};

watch(() => [gpsData.longitude, gpsData.latitude], ([newLng, newLat]) => {
  if (mapInstance && marker) {
    const BMapGL = window.BMapGL;
    const newPoint = new BMapGL.Point(newLng, newLat);
    marker.setPosition(newPoint);
    mapInstance.panTo(newPoint);
  }
});

const toggleTrend = () => {
  showTrendTable.value = !showTrendTable.value;
};

const goHistory = () => {
  router.push('/history');
};

const handleMessage = (message: any) => {
  if (!message || typeof message !== 'object') {
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
    status.blocked = Boolean(data.alarm_blocked);
    status.shortage = Boolean(data.alarm_no_seed);

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
  const url = `${wsBase}/ws/live?run_id=${runId}`;
  runStore.setWsStatus('connecting');
  wsClient = new ReconnectingWebSocket(
    url,
    handleMessage,
    () => runStore.setWsStatus('open'),
    () => runStore.setWsStatus('closed')
  );
};

const closeWebSocket = () => {
  if (wsClient) {
    wsClient.close();
    wsClient = null;
  }
  runStore.setWsStatus('closed');
};

const toggleRun = async () => {
  if (isRunning.value) {
    const runId = runStore.runId;
    closeWebSocket();
    if (runId) {
      await http.post(`/runs/${runId}/stop`);
    }
    runStore.setRunId(null);
    runStore.resetBuffers();
    return;
  }

  const response = await http.post('/runs/start', { machine_id: machineId });
  const runId = response.data?.run_id;
  if (!runId) {
    return;
  }
  runStore.setRunId(runId);
  runStore.resetBuffers();
  openWebSocket(runId);
};

onMounted(() => {
  setTimeout(initMap, 500);
});

onBeforeUnmount(() => {
  closeWebSocket();
});
</script>

<style scoped>
.monitor-container { 
  font-family: "Microsoft YaHei", sans-serif; 
  max-width: 1400px; 
  margin: 0 auto; 
  background-color: #fff; 
}

.header { display: flex; align-items: center; padding: 10px 20px; border-bottom: 2px solid #ccc; gap: 20px; }
.logo-section .logo { height: 60px; margin-right: 20px; }
.title-section h1 { font-size: 28px; margin: 0; letter-spacing: 2px; }
.header-actions { margin-left: auto; display: flex; gap: 10px; }
.action-btn { padding: 6px 12px; border: 1px solid #666; background: #f5f5f5; cursor: pointer; font-size: 14px; }

.main-content { 
  display: flex; 
  flex-direction: row; 
  border: 2px dashed #333; 
  margin: 20px; 
  min-height: 650px; 
}

.left-panel { 
  flex: 3; 
  padding: 30px; 
  display: flex; 
  flex-direction: column; 
  justify-content: space-between; 
}

.right-panel { 
  flex: 2; 
  border-left: 2px solid #000; 
  padding: 20px; 
  display: flex; 
  flex-direction: column; 
}

.data-grid { display: flex; flex-wrap: wrap; gap: 20px; }
.data-row { display: flex; align-items: center; width: 48%; margin-bottom: 25px; }
.data-row.full-width { width: 100%; }
.single-row { width: 100%; }

.data-row label { font-size: 20px; width: 160px; text-align: right; margin-right: 10px; }

.value-box { background-color: #5b9bd5; border: 1px solid #333; border-radius: 8px; height: 45px; flex-grow: 1; display: flex; align-items: center; justify-content: center; color: white; font-size: 22px; font-weight: bold; box-shadow: 2px 2px 5px rgba(0,0,0,0.2); }
.unit { font-size: 20px; margin-left: 10px; width: 40px; font-style: italic; font-family: "Times New Roman", serif; }

.indicators-area { display: flex; justify-content: space-around; margin-top: 40px; padding: 0 50px; }
.indicator-item { display: flex; flex-direction: column; align-items: center; }
.indicator-item span { font-size: 22px; margin-bottom: 15px; }
.bulb-icon { width: 80px; height: 80px; fill: white; stroke: black; stroke-width: 2px; transition: fill 0.3s ease; }
.bulb-icon.active { fill: #ff0000; stroke: #b30000; filter: drop-shadow(0 0 10px rgba(255, 0, 0, 0.8)); }

.map-title { text-align: center; font-size: 26px; margin-bottom: 10px; margin-top: 0; }
.coords-info { display: flex; justify-content: space-around; font-size: 20px; margin-bottom: 15px; }
.map-border { flex-grow: 1; border: 2px solid #999; position: relative; min-height: 300px; }
#baidu-map-container { width: 100%; height: 100%; background-color: #f0f0f0; }
.map-switch-btn { position: absolute; top: 10px; right: 10px; z-index: 999; padding: 8px 15px; background-color: rgba(255, 255, 255, 0.9); border: 1px solid #999; border-radius: 4px; font-size: 14px; cursor: pointer; box-shadow: 0 2px 5px rgba(0,0,0,0.3); font-weight: bold; transition: background 0.3s; }
.map-switch-btn:hover { background-color: #e6e6e6; }

@media (max-width: 900px) {
  .header { flex-direction: column; text-align: center; }
  .logo-section .logo { margin-right: 0; margin-bottom: 5px; height: 40px; }
  .title-section h1 { font-size: 18px; margin-bottom: 5px; }
  .header-actions { margin-left: 0; flex-wrap: wrap; justify-content: center; }

  .main-content {
    flex-direction: column;
    margin: 5px;
    border: 1px dashed #ccc;
  }

  .left-panel {
    padding: 10px;
    border-bottom: 1px solid #eee;
  }

  .data-grid {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 8px;
  }

  .data-row {
    width: 48%;
    margin-bottom: 0;
    flex-wrap: wrap; 
    justify-content: center;
    border: 1px solid #eee; 
    border-radius: 6px;
    padding: 8px 4px;
    background-color: rgba(240, 240, 240, 0.5);
  }

  .data-row.full-width { width: 100%; }

  .single-row { width: 100%; }

  .data-row label {
    width: 100%;
    text-align: center;
    margin-right: 0;
    font-size: 13px;
    margin-bottom: 5px;
    color: #333;
  }

  .value-box {
    height: 35px;
    font-size: 18px;
    min-width: 60px; 
  }

  .unit {
    font-size: 12px;
    margin-left: 4px;
    width: auto;
  }

  .indicators-area { margin-top: 15px; padding: 0; }
  .bulb-icon { width: 45px; height: 45px; }
  .indicator-item span { font-size: 14px; }

  .right-panel {
    border-left: none;
    padding: 10px;
    height: 400px;
  }
  .map-title { font-size: 18px; }
  .coords-info { font-size: 12px; flex-direction: column; align-items: center; gap: 6px; }
}
</style>
