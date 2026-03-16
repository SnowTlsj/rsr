<template>
  <div class="history-container">
    <header class="history-header">
      <div class="title-wrap">
        <h2>历史播种数据</h2>
        <p>选择任务后可查看轨迹、生成报告和导出数据</p>
      </div>
      <button class="back-btn" @click="goBack">返回监控</button>
    </header>

    <div class="history-body">
      <HistoryRunsList
        :runs="displayRuns"
        :selected-run-id="selectedRunId"
        :loading="loading"
        :load-error="loadError"
        :keyword="keyword"
        :sort-mode="sortMode"
        :report-loading="reportLoading"
        :exporting="exporting"
        @update:keyword="keyword = $event"
        @update:sort-mode="sortMode = $event"
        @refresh="loadRuns"
        @select="selectRun"
        @report="showReport"
        @export="exportRunData"
        @delete="deleteRun"
      />

      <HistoryMapPanel
        :selected-run="selectedRun"
        :selected-run-id="selectedRunId"
        :gps-point-count="gpsPoints.length"
        :map-loading="mapLoading"
        @zoom-in="zoomIn"
        @zoom-out="zoomOut"
      />
    </div>

    <ReportModal
      :visible="reportVisible"
      :report="reportData"
      :exporting="exporting || reportLoading"
      @close="reportVisible = false"
      @export-pdf="handleExportPDF"
      @export-excel="handleExportExcel"
    />

    <Toast :visible="toastVisible" :message="toastMessage" :type="toastType" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import Toast from '@/components/Toast.vue';
import ReportModal from '@/components/ReportModal.vue';
import HistoryMapPanel from '@/components/history/HistoryMapPanel.vue';
import HistoryRunsList from '@/components/history/HistoryRunsList.vue';
import { http } from '@/api/http';
import { HISTORY_DAYS, HISTORY_MAP_LIMIT, HISTORY_MAP_TARGET_POINTS } from '@/constants/history';
import { useHistoryMap } from '@/composables/useHistoryMap';
import { useHistoryReports } from '@/composables/useHistoryReports';
import { useToast } from '@/composables/useToast';
import type { RunSummary } from '@/types/history';
import { extractErrorMessage, isAuthError } from '@/utils/httpError';

const router = useRouter();
const { toastMessage, toastType, toastVisible, success, error, warning, info } = useToast();

const runs = ref<RunSummary[]>([]);
const selectedRunId = ref<string | null>(null);
const selectedRun = ref<RunSummary | null>(null);
const loading = ref(false);
const loadError = ref('');
const keyword = ref('');
const sortMode = ref<'time_desc' | 'time_asc' | 'name_asc' | 'name_desc'>('time_desc');
const defaultLongitude = parseFloat(import.meta.env.VITE_DEFAULT_LONGITUDE) || 116.3650;
const defaultLatitude = parseFloat(import.meta.env.VITE_DEFAULT_LATITUDE) || 40.0095;
const {
  exporting,
  reportLoading,
  reportVisible,
  reportData,
  showReport,
  exportRunData,
  handleExportPDF,
  handleExportExcel
} = useHistoryReports({ success, error, warning, info });
const { gpsPoints, mapLoading, initMap, renderPath, zoomIn, zoomOut, clearMap } = useHistoryMap(
  { warning },
  defaultLongitude,
  defaultLatitude
);

const resolveRequestErrorMessage = (requestError: unknown, fallback: string) => {
  if (isAuthError(requestError)) {
    return '管理会话已失效，请重新登录';
  }
  return extractErrorMessage(requestError, fallback);
};

const displayRuns = computed(() => {
  const search = keyword.value.toLowerCase();
  const filtered = runs.value.filter((run) => run.run_name.toLowerCase().includes(search));
  return filtered.sort((a, b) => {
    switch (sortMode.value) {
      case 'time_asc':
        return new Date(a.started_at).getTime() - new Date(b.started_at).getTime();
      case 'name_asc':
        return a.run_name.localeCompare(b.run_name, 'zh-CN');
      case 'name_desc':
        return b.run_name.localeCompare(a.run_name, 'zh-CN');
      case 'time_desc':
      default:
        return new Date(b.started_at).getTime() - new Date(a.started_at).getTime();
    }
  });
});

const loadRuns = async () => {
  loading.value = true;
  loadError.value = '';
  try {
    const response = await http.get('/runs', { params: { days: HISTORY_DAYS } });
    runs.value = response.data || [];
    if (runs.value.length === 0) {
      info('暂无历史记录');
    }
  } catch (requestError) {
    loadError.value = resolveRequestErrorMessage(requestError, '加载失败，请检查网络后重试');
    error(loadError.value);
  } finally {
    loading.value = false;
  }
};

const selectRun = async (runId: string) => {
  selectedRunId.value = runId;
  selectedRun.value = runs.value.find((run) => run.run_id === runId) || null;
  mapLoading.value = true;
  try {
    const response = await http.get(`/runs/${runId}/gps`, {
      params: { limit: HISTORY_MAP_LIMIT, target_points: HISTORY_MAP_TARGET_POINTS }
    });
    gpsPoints.value = response.data || [];
    if (gpsPoints.value.length === 0) {
      warning('该任务暂无GPS轨迹数据');
    }
    renderPath();
  } catch (requestError) {
    error(resolveRequestErrorMessage(requestError, '加载GPS轨迹失败，请重试'));
  } finally {
    mapLoading.value = false;
  }
};

const deleteRun = async (run: RunSummary) => {
  if (!confirm(`确定要删除记录 "${run.run_name}" 吗？此操作不可恢复。`)) {
    return;
  }

  try {
    await http.delete(`/runs/${run.run_id}`);
    success('删除成功');
    runs.value = runs.value.filter((item) => item.run_id !== run.run_id);
    if (selectedRunId.value === run.run_id) {
      selectedRunId.value = null;
      selectedRun.value = null;
      clearMap();
    }
  } catch (requestError) {
    error(resolveRequestErrorMessage(requestError, '删除失败，请重试'));
  }
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
.history-container { padding: 16px; width: 100%; min-height: 100vh; margin: 0; font-family: var(--font-main); color: var(--c-text-primary); }
.history-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid var(--c-border); padding-bottom: 12px; gap: 12px; }
.title-wrap h2 { margin: 0; font-size: 26px; color: var(--c-text-primary); font-weight: 800; }
.title-wrap p { margin: 3px 0 0; color: var(--c-text-secondary); font-size: 13px; }
.back-btn {
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
.back-btn:hover { background: linear-gradient(140deg, #f6e8d8 0%, #e9d1b4 100%); border-color: #8f653f; }
.history-body { display: grid; grid-template-columns: 320px 1fr; gap: 12px; min-height: calc(100vh - 132px); }

@media (max-width: 900px) {
  .history-container { padding: 10px; }
  .history-header { flex-direction: column; align-items: stretch; }
  .title-wrap h2 { font-size: 20px; }
  .back-btn { font-size: 13px; padding: 8px 12px; }
  .history-body { grid-template-columns: 1fr; min-height: auto; }
}
</style>
