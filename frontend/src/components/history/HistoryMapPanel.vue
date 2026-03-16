<template>
  <section class="map-section">
    <div v-if="selectedRun" class="run-info">
      <div><strong>任务:</strong> {{ selectedRun.run_name }}</div>
      <div><strong>开始:</strong> {{ formatTime(selectedRun.started_at) }}</div>
      <div><strong>结束:</strong> {{ selectedRun.ended_at ? formatTime(selectedRun.ended_at) : '进行中' }}</div>
      <div><strong>轨迹点:</strong> {{ gpsPointCount }}</div>
    </div>
    <div class="map-frame">
      <div v-if="mapLoading || !selectedRunId" class="map-overlay">
        <StateBlock
          v-if="mapLoading"
          title="轨迹加载中..."
          description="正在准备地图轨迹，请稍候。"
          variant="loading"
        />
        <StateBlock
          v-else
          title="请选择任务"
          description="从左侧列表选择一条播种记录后，这里会显示轨迹与任务概览。"
          variant="empty"
        />
      </div>
      <div id="history-map"></div>
      <div class="map-controls">
        <button class="map-ctrl-btn" type="button" title="放大" @click="emit('zoom-in')">+</button>
        <button class="map-ctrl-btn" type="button" title="缩小" @click="emit('zoom-out')">-</button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import StateBlock from '@/components/StateBlock.vue';
import type { RunSummary } from '@/types/history';

defineProps<{
  selectedRun: RunSummary | null;
  selectedRunId: string | null;
  gpsPointCount: number;
  mapLoading: boolean;
}>();

const emit = defineEmits<{
  'zoom-in': [];
  'zoom-out': [];
}>();

const formatTime = (value: string) => new Date(value).toLocaleString('zh-CN');
</script>

<style scoped>
.map-section { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.run-info { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; font-size: 13px; padding: 10px; background: #fff; border-radius: 10px; flex-wrap: wrap; color: var(--c-text-primary); border: 1px solid var(--c-border); box-shadow: var(--shadow-sm); }
.run-info > div { background: #f8fbff; border: 1px solid #dde8f4; border-radius: 8px; padding: 8px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.map-frame { flex: 1; border: 1px solid var(--c-border-strong); min-height: 500px; border-radius: 12px; overflow: hidden; position: relative; background: var(--c-bg-panel); box-shadow: var(--shadow-md); }
#history-map { width: 100%; height: 100%; min-height: 500px; }
.map-overlay { position: absolute; top: 10px; left: 10px; z-index: 1000; width: min(320px, calc(100% - 20px)); }
.map-controls { position: absolute; top: 10px; right: 10px; z-index: 999; display: flex; flex-direction: column; gap: 6px; }
.map-ctrl-btn { width: 34px; height: 34px; border: 1px solid #9bb1c8; background: rgba(255, 255, 255, 0.96); border-radius: 8px; font-size: 18px; font-weight: bold; cursor: pointer; box-shadow: var(--shadow-sm); }
.map-ctrl-btn:hover { background: #edf5ff; }

@media (max-width: 900px) {
  .run-info { grid-template-columns: 1fr; }
  .map-frame { min-height: 400px; }
  #history-map { min-height: 400px; }
}
</style>
