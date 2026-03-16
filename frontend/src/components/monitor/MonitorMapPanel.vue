<template>
  <div class="right-panel">
    <h2 class="map-title">地图定位</h2>
    <div class="coords-info">
      <span>经度: {{ longitude.toFixed(6) }} E</span>
      <span>纬度: {{ latitude.toFixed(6) }} N</span>
    </div>
    <div class="map-border">
      <div id="baidu-map-container"></div>
      <button class="map-switch-btn" @click="emit('toggle-map-mode')">
        {{ isSatelliteMode ? '切换二维地图' : '切换卫星实景' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  longitude: number;
  latitude: number;
  isSatelliteMode: boolean;
}>();

const emit = defineEmits<{
  'toggle-map-mode': [];
}>();
</script>

<style scoped>
.right-panel { border-left: 1px solid rgba(157, 176, 200, 0.7); padding: 14px; display: flex; flex-direction: column; background: rgba(248, 251, 255, 0.75); }
.map-title { text-align: left; font-size: 26px; margin-bottom: 8px; margin-top: 0; color: var(--c-text-primary); font-weight: 800; }
.coords-info { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 16px; margin-bottom: 8px; color: #334155; background: rgba(255, 255, 255, 0.85); border: 1px solid rgba(215, 227, 240, 0.9); border-radius: 10px; padding: 8px 10px; white-space: nowrap; }
.map-border { flex-grow: 1; border: 1px solid var(--c-border-strong); position: relative; min-height: 300px; border-radius: 10px; overflow: hidden; box-shadow: var(--shadow-sm); height: min(68vh, 760px); }
#baidu-map-container { width: 100%; height: 100%; background-color: #f0f0f0; }
.map-switch-btn { position: absolute; top: 10px; right: 10px; z-index: 999; padding: 8px 12px; background-color: rgba(255, 255, 255, 0.96); border: 1px solid var(--c-border); border-radius: 999px; font-size: 13px; cursor: pointer; box-shadow: var(--shadow-sm); font-weight: 700; color: var(--c-text-primary); }
.map-switch-btn:hover { background-color: #eef4fb; }

@media (max-width: 900px) {
  .right-panel { border-left: none; padding: 10px; min-height: 420px; }
  .map-title { font-size: 20px; }
  .coords-info { font-size: 13px; flex-direction: column; align-items: flex-start; white-space: normal; }
  .map-switch-btn { font-size: 12px; }
}
</style>
