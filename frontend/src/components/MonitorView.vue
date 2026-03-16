<template>
  <div class="monitor-container" :style="containerStyle">
    <div class="theme-background" :style="backgroundLayerStyle" aria-hidden="true"></div>
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
        <button class="action-btn" :disabled="isSyncPending || isRunActionPending" title="手动同步任务状态" @click="manualSync">
          {{ isSyncPending ? '同步中...' : '同步' }}
        </button>
        <button class="action-btn" @click="goHistory">历史数据</button>
      </div>
    </header>

    <RunStatusBar
      :visible="isRunning"
      :current-task-name="currentTaskName"
      :run-id="runStore.runId"
      :connection-status-text="connectionStatusText"
      :connection-status-class="connectionStatusClass"
      :last-heartbeat-text="lastHeartbeatText"
    />

    <main class="main-content">
      <MonitorDataPanel
        :sensor-data="sensorData"
        :alarm-data="alarmData"
        :total-sowing="totalSowing"
        :uniformity-index="uniformityIndex"
        :mascot-x="mascotPos.x"
        :mascot-y="mascotPos.y"
        :aroma-particles="aromaParticles"
        @mascot-pointer-down="onMascotPointerDown"
        @mascot-activate="emitAroma"
      />

      <MonitorMapPanel
        :longitude="gpsData.longitude"
        :latitude="gpsData.latitude"
        :is-satellite-mode="isSatelliteMode"
        @toggle-map-mode="toggleMapMode"
      />
    </main>

    <Toast :visible="toastVisible" :message="toastMessage" :type="toastType" />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import Toast from '@/components/Toast.vue';
import MonitorDataPanel from '@/components/monitor/MonitorDataPanel.vue';
import MonitorMapPanel from '@/components/monitor/MonitorMapPanel.vue';
import RunStatusBar from '@/components/monitor/RunStatusBar.vue';
import { useMascotAroma } from '@/composables/useMascotAroma';
import { useMonitorMap } from '@/composables/useMonitorMap';
import { useMonitorRealtime } from '@/composables/useMonitorRealtime';
import { useThemeBackground } from '@/composables/useThemeBackground';
import { useToast } from '@/composables/useToast';

const router = useRouter();
const defaultLongitude = parseFloat(import.meta.env.VITE_DEFAULT_LONGITUDE) || 116.3650;
const defaultLatitude = parseFloat(import.meta.env.VITE_DEFAULT_LATITUDE) || 40.0095;

const { toastMessage, toastType, toastVisible, success, error, warning, info } = useToast();
const { activeTheme, bgOpacity, containerStyle, backgroundLayerStyle, hydrate } = useThemeBackground();
const { aromaParticles, mascotPos, onMascotPointerDown, emitAroma, bind, unbind } = useMascotAroma();
let resetTrail = () => {};

const {
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
  startHeartbeatMonitor
} = useMonitorRealtime({
  toast: { success, error, warning, info },
  defaultLongitude,
  defaultLatitude,
  onRunStarted: () => resetTrail(),
  onRunStopped: () => resetTrail()
});
const monitorMap = useMonitorMap(gpsData, { error, warning });
const { isSatelliteMode, initMap, toggleMapMode } = monitorMap;
resetTrail = monitorMap.resetTrail;

const goHistory = () => {
  router.push('/history');
};

onMounted(async () => {
  bind();
  hydrate();
  setTimeout(initMap, 500);
  await checkActiveRun();
  startHeartbeatMonitor();
});

onBeforeUnmount(() => {
  unbind();
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

.theme-background {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background-size: cover, auto, auto, auto, auto;
  background-position: center center, center, center, center, center;
  background-repeat: no-repeat, no-repeat, no-repeat, no-repeat, no-repeat;
}

.header {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  padding: 10px 18px;
  border-bottom: 1px solid var(--c-border);
  gap: 14px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(2px);
}

.logo-section .logo {
  height: 72px;
  max-width: 460px;
  width: auto;
  margin-right: 8px;
  object-fit: contain;
}

.title-section {
  flex: 1;
  min-width: 0;
}

.title-section h1 {
  font-size: 26px;
  margin: 0;
  letter-spacing: 0.4px;
  color: var(--c-text-primary);
  font-weight: 800;
  line-height: 1.2;
}

.style-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border: 1px solid #b08962;
  background: linear-gradient(135deg, #ead6bb 0%, #d9bea0 100%);
  border-radius: 999px;
  color: #5f4329;
  font-size: 12px;
  font-weight: 700;
  box-shadow: inset 0 -1px 0 rgba(99, 68, 42, 0.2);
}

.style-controls select {
  border: 1px solid #b08962;
  border-radius: 999px;
  background: #f4e6d4;
  color: #5f4329;
  font-size: 12px;
  padding: 4px 8px;
  outline: none;
}

.style-controls input {
  width: 88px;
  accent-color: #8c5d31;
}

.header-actions {
  margin-left: auto;
  display: flex;
  gap: 10px;
}

.action-btn {
  padding: 10px 18px;
  border: 1px solid #a47a51;
  background: linear-gradient(140deg, #f2e1cc 0%, #e3c7a6 100%);
  cursor: pointer;
  font-size: 16px;
  border-radius: 999px;
  transition: all 0.2s;
  color: #5d3f24;
  font-weight: 700;
  white-space: nowrap;
  box-shadow: inset 0 -1px 0 rgba(100, 68, 38, 0.18);
}

.action-btn:hover {
  background: linear-gradient(140deg, #f6e8d8 0%, #e9d1b4 100%);
  border-color: #8f653f;
}

.action-btn.active {
  background: #dc2626;
  color: white;
  border-color: #dc2626;
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.main-content {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  border: 1px solid rgba(157, 176, 200, 0.7);
  margin: 12px;
  min-height: calc(100vh - 110px);
  flex: 1;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: var(--shadow-md);
  border-radius: 14px;
  overflow: hidden;
  backdrop-filter: blur(1px);
}

@media (max-width: 900px) {
  .header {
    flex-direction: column;
    text-align: center;
    gap: 10px;
  }

  .logo-section .logo {
    margin-right: 0;
    margin-bottom: 5px;
    height: 40px;
  }

  .title-section h1 {
    font-size: 26px;
    margin-bottom: 5px;
  }

  .style-controls {
    order: 3;
    width: 100%;
    justify-content: center;
  }

  .header-actions {
    margin-left: 0;
    flex-wrap: wrap;
    justify-content: center;
  }

  .action-btn {
    font-size: 13px;
    padding: 8px 12px;
  }

  .main-content {
    grid-template-columns: 1fr;
    margin: 8px;
    min-height: calc(100vh - 92px);
  }
}
</style>
