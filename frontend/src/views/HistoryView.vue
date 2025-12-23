<template>
  <div class="history-container">
    <header class="history-header">
      <h2>History Runs</h2>
      <button class="back-btn" @click="goBack">Back</button>
    </header>

    <div class="history-body">
      <aside class="runs-list">
        <div class="list-title">Runs (last 30 days)</div>
        <ul>
          <li
            v-for="run in runs"
            :key="run.id"
            :class="{ active: run.id === selectedRunId }"
            @click="selectRun(run.id)"
          >
            <div class="run-name">{{ run.run_name }}</div>
            <div class="run-time">{{ formatTime(run.started_at) }}</div>
          </li>
        </ul>
      </aside>

      <section class="map-section">
        <div class="run-info" v-if="selectedRun">
          <div>Run: {{ selectedRun.run_name }}</div>
          <div>Start: {{ formatTime(selectedRun.started_at) }}</div>
          <div>End: {{ selectedRun.ended_at ? formatTime(selectedRun.ended_at) : '-' }}</div>
          <div>Points: {{ gpsPoints.length }}</div>
        </div>
        <div class="map-frame">
          <div id="history-map"></div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { http } from '@/api/http';

interface RunSummary {
  id: string;
  machine_id: string;
  run_name: string;
  started_at: string;
  ended_at: string | null;
}

interface GpsPoint {
  ts: string;
  lon: number;
  lat: number;
  alt_m?: number;
  heading_deg?: number;
}

const router = useRouter();
const runs = ref<RunSummary[]>([]);
const selectedRunId = ref<string | null>(null);
const selectedRun = ref<RunSummary | null>(null);
const gpsPoints = ref<GpsPoint[]>([]);

let mapInstance: any = null;
let overlay: any = null;

const machineId = import.meta.env.VITE_MACHINE_ID || '';

const initMap = () => {
  const BMapGL = window.BMapGL;
  if (!BMapGL) {
    return;
  }
  mapInstance = new BMapGL.Map('history-map');
  const point = new BMapGL.Point(116.404, 39.915);
  mapInstance.centerAndZoom(point, 14);
  mapInstance.enableScrollWheelZoom(true);
};

const loadRuns = async () => {
  const response = await http.get('/runs', {
    params: { days: 30, machine_id: machineId }
  });
  runs.value = response.data || [];
};

const selectRun = async (runId: string) => {
  selectedRunId.value = runId;
  selectedRun.value = runs.value.find((run) => run.id === runId) || null;
  const response = await http.get(`/runs/${runId}/gps`, { params: { limit: 100000 } });
  gpsPoints.value = response.data || [];
  renderPath();
};

const renderPath = () => {
  if (!mapInstance) {
    return;
  }
  mapInstance.clearOverlays();
  overlay = null;

  const BMapGL = window.BMapGL;
  const points = gpsPoints.value.map((p) => new BMapGL.Point(p.lon, p.lat));
  if (!points.length) {
    return;
  }
  mapInstance.centerAndZoom(points[0], 17);

  if (BMapGL.PointCollection) {
    const options = { size: 4, shape: BMAP_POINT_SHAPE_CIRCLE, color: '#e53935' };
    overlay = new BMapGL.PointCollection(points, options);
    mapInstance.addOverlay(overlay);
  } else {
    points.forEach((point: any) => {
      const marker = new BMapGL.Marker(point);
      mapInstance.addOverlay(marker);
    });
  }
};

const formatTime = (value: string) => {
  return new Date(value).toLocaleString();
};

const goBack = () => {
  router.push('/');
};

onMounted(async () => {
  initMap();
  await loadRuns();
});
</script>

<style scoped>
.history-container {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.back-btn {
  padding: 6px 12px;
  border: 1px solid #666;
  background: #f5f5f5;
  cursor: pointer;
}

.history-body {
  display: flex;
  gap: 20px;
}

.runs-list {
  width: 260px;
  border: 1px solid #ccc;
  padding: 10px;
  max-height: 700px;
  overflow: auto;
}

.runs-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.runs-list li {
  padding: 8px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
}

.runs-list li.active {
  background: #e6f2ff;
}

.run-name {
  font-weight: 600;
  font-size: 14px;
}

.run-time {
  font-size: 12px;
  color: #666;
}

.map-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.run-info {
  display: flex;
  gap: 20px;
  font-size: 14px;
}

.map-frame {
  flex: 1;
  border: 2px solid #999;
  min-height: 500px;
}

#history-map {
  width: 100%;
  height: 100%;
}

@media (max-width: 900px) {
  .history-body {
    flex-direction: column;
  }

  .runs-list {
    width: 100%;
    max-height: 240px;
  }

  .run-info {
    flex-direction: column;
  }
}
</style>
