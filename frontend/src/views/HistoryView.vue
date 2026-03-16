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
      <aside class="runs-list">
        <div class="list-title">播种记录 (最近30天)</div>
        <div class="list-tools">
          <input v-model.trim="keyword" class="tool-input" placeholder="搜索任务名称" aria-label="搜索任务名称" />
          <select v-model="sortMode" class="tool-select" aria-label="排序方式">
            <option value="time_desc">时间倒序</option>
            <option value="time_asc">时间正序</option>
            <option value="name_asc">名称 A-Z</option>
            <option value="name_desc">名称 Z-A</option>
          </select>
          <button class="tool-refresh" type="button" :disabled="loading" @click="loadRuns">
            {{ loading ? '刷新中...' : '刷新' }}
          </button>
        </div>
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="loadError" class="load-error">
          <span>{{ loadError }}</span>
          <button class="tool-refresh" @click="loadRuns">重试</button>
        </div>
        <ul v-else>
          <li v-for="run in displayRuns" :key="run.run_id" :class="{ active: run.run_id === selectedRunId }">
            <button type="button" @click="selectRun(run.run_id)" class="run-item" :aria-label="`查看任务 ${run.run_name}`">
              <div class="run-name">{{ run.run_name }}</div>
              <div class="run-time">{{ formatTime(run.started_at) }}</div>
            </button>
            <div class="action-buttons">
              <button
                class="action-btn report-btn"
                type="button"
                @click.stop="showReport(run)"
                :disabled="reportLoading || exporting"
                title="查看报告"
              >
                {{ reportLoading ? '生成中...' : '报告' }}
              </button>
              <button
                class="action-btn export-btn"
                type="button"
                @click.stop="exportRunData(run)"
                :disabled="exporting"
                title="导出Excel"
              >
                {{ exporting ? '导出中...' : '导出' }}
              </button>
              <button
                class="action-btn delete-btn"
                type="button"
                @click.stop="deleteRun(run)"
                :disabled="reportLoading || exporting"
                title="删除记录"
              >
                删除
              </button>
            </div>
          </li>
          <li v-if="displayRuns.length === 0" class="empty">暂无记录</li>
        </ul>
      </aside>

      <section class="map-section">
        <div class="run-info" v-if="selectedRun">
          <div><strong>任务:</strong> {{ selectedRun.run_name }}</div>
          <div><strong>开始:</strong> {{ formatTime(selectedRun.started_at) }}</div>
          <div><strong>结束:</strong> {{ selectedRun.ended_at ? formatTime(selectedRun.ended_at) : '进行中' }}</div>
          <div><strong>轨迹点:</strong> {{ gpsPoints.length }}</div>
        </div>
        <div class="map-frame">
          <div v-if="mapLoading" class="map-loading">轨迹加载中...</div>
          <div v-else-if="!selectedRunId" class="map-empty">请选择左侧任务查看轨迹</div>
          <div id="history-map"></div>
          <div class="map-controls">
            <button class="map-ctrl-btn" type="button" @click="zoomIn" title="放大">+</button>
            <button class="map-ctrl-btn" type="button" @click="zoomOut" title="缩小">-</button>
          </div>
        </div>
      </section>
    </div>

    <!-- 报告弹窗 -->
    <ReportModal
      :visible="reportVisible"
      :report="reportData"
      :exporting="exporting || reportLoading"
      @close="reportVisible = false"
      @export-pdf="handleExportPDF"
      @export-excel="handleExportExcel"
    />

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
import { onBeforeUnmount, onMounted, ref, reactive, computed } from 'vue';
import { useRouter } from 'vue-router';
import { http } from '@/api/http';
import * as XLSX from 'xlsx';
import ReportModal from '@/components/ReportModal.vue';
import { isAuthError } from '@/utils/httpError';

interface RunSummary {
  run_id: string;
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

interface ReportData {
  run_id: string;
  run_name: string;
  started_at: string;
  ended_at: string;
  duration: string;
  total_seed_kg: string;
  total_distance_km: string;
  leak_distance_km: string;
  avg_speed_kmh: string;
  uniformity_index: string;
  channel1_kg: string;
  channel2_kg: string;
  channel3_kg: string;
  channel4_kg: string;
  channel5_kg: string;
  alarm_blocked_count: number;
  alarm_no_seed_count: number;
  gps_point_count: number;
  start_location: string;
  end_location: string;
  trend_data: Array<{
    time: string;
    channel1: number;
    channel2: number;
    channel3: number;
    channel4: number;
    channel5: number;
  }>;
}

const router = useRouter();
const runs = ref<RunSummary[]>([]);
const selectedRunId = ref<string | null>(null);
const selectedRun = ref<RunSummary | null>(null);
const gpsPoints = ref<GpsPoint[]>([]);
const loading = ref(false);
const loadError = ref('');
const exporting = ref(false);
const reportLoading = ref(false);
const mapLoading = ref(false);
const keyword = ref('');
const sortMode = ref<'time_desc' | 'time_asc' | 'name_asc' | 'name_desc'>('time_desc');

// 报告相关状态
const reportVisible = ref(false);
const reportData = ref<ReportData>({
  run_id: '',
  run_name: '', started_at: '', ended_at: '', duration: '',
  total_seed_kg: '0', total_distance_km: '0', leak_distance_km: '0', avg_speed_kmh: '0',
  uniformity_index: '0',
  channel1_kg: '0', channel2_kg: '0', channel3_kg: '0', channel4_kg: '0', channel5_kg: '0',
  alarm_blocked_count: 0, alarm_no_seed_count: 0, gps_point_count: 0,
  start_location: '-', end_location: '-', trend_data: []
});
const reportRun = ref<RunSummary | null>(null);
const reportGps = ref<GpsPoint[]>([]);
const reportTelemetry = ref<Record<string, any>[]>([]);

let mapInstance: any = null;
let overlay: any = null;

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
  const defaultLongitude = parseFloat(import.meta.env.VITE_DEFAULT_LONGITUDE) || 116.3650;
  const defaultLatitude = parseFloat(import.meta.env.VITE_DEFAULT_LATITUDE) || 40.0095;
  mapInstance = new BMapGL.Map('history-map');
  const point = new BMapGL.Point(defaultLongitude, defaultLatitude);
  mapInstance.centerAndZoom(point, 14);
  mapInstance.enableScrollWheelZoom(true);
};

const loadRuns = async () => {
  loading.value = true;
  loadError.value = '';
  try {
    const response = await http.get('/runs', { params: { days: 30 } });
    runs.value = response.data || [];
    if (runs.value.length === 0) {
      showToast('暂无历史记录', 'info');
    }
  } catch (e) {
    console.error('Load runs failed', e);
    loadError.value = '加载失败，请检查网络后重试';
    if (isAuthError(e)) {
      showToast('加载失败：鉴权无效，请检查管理令牌', 'error');
    } else {
      showToast('加载历史记录失败，请重试', 'error');
    }
  } finally {
    loading.value = false;
  }
};

const selectRun = async (runId: string) => {
  selectedRunId.value = runId;
  selectedRun.value = runs.value.find((run) => run.run_id === runId) || null;
  mapLoading.value = true;
  try {
    const response = await http.get(`/runs/${runId}/gps`, { params: { limit: 100000 } });
    gpsPoints.value = response.data || [];
    if (gpsPoints.value.length === 0) {
      showToast('该任务暂无GPS轨迹数据', 'warning');
    } else {
      showToast(`加载了 ${gpsPoints.value.length} 个轨迹点`, 'success', 2000);
    }
    renderPath();
  } catch (e) {
    console.error('Load GPS failed', e);
    if (isAuthError(e)) {
      showToast('加载轨迹失败：鉴权无效，请检查管理令牌', 'error');
    } else {
      showToast('加载GPS轨迹失败，请重试', 'error');
    }
  } finally {
    mapLoading.value = false;
  }
};

const renderPath = () => {
  if (!mapInstance) return;
  mapInstance.clearOverlays();
  overlay = null;

  const BMapGL = (window as any).BMapGL;
  const points = gpsPoints.value.map((p) => new BMapGL.Point(p.lon, p.lat));
  if (!points.length) return;

  // 自动缩放到合适位置显示所有轨迹点
  if (points.length > 1) {
    const viewport = mapInstance.getViewport(points);
    mapInstance.centerAndZoom(viewport.center, viewport.zoom);
  } else {
    mapInstance.centerAndZoom(points[0], 17);
  }

  if (BMapGL.PointCollection) {
    const options = { size: 4, shape: (window as any).BMAP_POINT_SHAPE_CIRCLE, color: '#e53935' };
    overlay = new BMapGL.PointCollection(points, options);
    mapInstance.addOverlay(overlay);
  } else {
    points.forEach((point: any) => {
      const marker = new BMapGL.Marker(point);
      mapInstance.addOverlay(marker);
    });
  }
};

// 地图缩放控制
const zoomIn = () => {
  if (mapInstance) {
    const currentZoom = mapInstance.getZoom();
    mapInstance.setZoom(currentZoom + 1);
  }
};

const zoomOut = () => {
  if (mapInstance) {
    const currentZoom = mapInstance.getZoom();
    mapInstance.setZoom(currentZoom - 1);
  }
};

// 删除记录
const deleteRun = async (run: RunSummary) => {
  if (!confirm(`确定要删除记录 "${run.run_name}" 吗？此操作不可恢复。`)) {
    return;
  }
  try {
    await http.delete(`/runs/${run.run_id}`);
    showToast('删除成功', 'success');
    // 从列表中移除
    runs.value = runs.value.filter(r => r.run_id !== run.run_id);
    // 如果删除的是当前选中的，清空选中状态
    if (selectedRunId.value === run.run_id) {
      selectedRunId.value = null;
      selectedRun.value = null;
      gpsPoints.value = [];
      if (mapInstance) {
        mapInstance.clearOverlays();
      }
    }
  } catch (e) {
    console.error('Delete run failed', e);
    if (isAuthError(e)) {
      showToast('删除失败：鉴权无效，请检查管理令牌', 'error');
    } else {
      showToast('删除失败，请重试', 'error');
    }
  }
};

const formatTime = (value: string) => new Date(value).toLocaleString('zh-CN');
const goBack = () => { router.push('/'); };

// 生成报告
const showReport = async (run: RunSummary) => {
  if (reportLoading.value) {
    return;
  }
  reportLoading.value = true;
  try {
    showToast('正在生成报告...', 'info');

    // 并行获取数据
    const [gpsResponse, telemetryResponse] = await Promise.all([
      http.get(`/runs/${run.run_id}/gps`, { params: { limit: 100000 } }),
      http.get(`/runs/${run.run_id}/telemetry`, { params: { bucket: '1s' } })
    ]);

    const gpsData = gpsResponse.data || [];
    const telemetryData = telemetryResponse.data || [];

    // 计算统计数据
    const duration = run.ended_at
      ? Math.round((new Date(run.ended_at).getTime() - new Date(run.started_at).getTime()) / 1000 / 60)
      : 0;

    const lastTelemetry = telemetryData.length > 0 ? telemetryData[telemetryData.length - 1] : null;

    // 计算告警次数（使用新的 alarm_channel 字段）
    let alarmBlocked = 0;
    let alarmNoSeed = 0;
    telemetryData.forEach((d: any) => {
      // 检查新的通道警报
      if (d.alarm_channel1 || d.alarm_channel2 || d.alarm_channel3 || d.alarm_channel4 || d.alarm_channel5) {
        alarmBlocked++;
      }
      // 兼容旧字段
      if (d.alarm_blocked) alarmBlocked++;
      if (d.alarm_no_seed) alarmNoSeed++;
    });

    // GPS 位置
    const startGps = gpsData.length > 0 ? gpsData[0] : null;
    const endGps = gpsData.length > 0 ? gpsData[gpsData.length - 1] : null;

    // 趋势数据（取样，最多100个点）
    const sampleRate = Math.max(1, Math.floor(telemetryData.length / 100));
    const trendData = telemetryData
      .filter((_: any, i: number) => i % sampleRate === 0)
      .map((d: any) => ({
        time: new Date(d.ts).toLocaleTimeString('zh-CN'),
        channel1: d.channel1_g || 0,
        channel2: d.channel2_g || 0,
        channel3: d.channel3_g || 0,
        channel4: d.channel4_g || 0,
        channel5: d.channel5_g || 0
      }));

    // 匀播指数 = 总播种量 / 总里程
    let uniformityIndex = '0.00';
    if (lastTelemetry) {
      const total = lastTelemetry.seed_total_g || 0;
      const distance = lastTelemetry.distance_m || 0;
      if (distance > 0 && total > 0) {
        uniformityIndex = (total / distance).toFixed(2);
      }
    }

    reportData.value = {
      run_id: run.run_id,
      run_name: run.run_name,
      started_at: run.started_at,
      ended_at: run.ended_at || '-',
      duration: `${duration} 分钟`,
      total_seed_kg: lastTelemetry?.seed_total_g ? (lastTelemetry.seed_total_g / 1000).toFixed(2) : '0',
      total_distance_km: lastTelemetry?.distance_m ? (lastTelemetry.distance_m / 1000).toFixed(2) : '0',
      leak_distance_km: lastTelemetry?.leak_distance_m ? (lastTelemetry.leak_distance_m / 1000).toFixed(2) : '0',
      avg_speed_kmh: lastTelemetry?.speed_kmh ? lastTelemetry.speed_kmh.toFixed(2) : '0',
      uniformity_index: uniformityIndex,
      channel1_kg: lastTelemetry?.channel1_g ? (lastTelemetry.channel1_g / 1000).toFixed(2) : '0',
      channel2_kg: lastTelemetry?.channel2_g ? (lastTelemetry.channel2_g / 1000).toFixed(2) : '0',
      channel3_kg: lastTelemetry?.channel3_g ? (lastTelemetry.channel3_g / 1000).toFixed(2) : '0',
      channel4_kg: lastTelemetry?.channel4_g ? (lastTelemetry.channel4_g / 1000).toFixed(2) : '0',
      channel5_kg: lastTelemetry?.channel5_g ? (lastTelemetry.channel5_g / 1000).toFixed(2) : '0',
      alarm_blocked_count: alarmBlocked,
      alarm_no_seed_count: alarmNoSeed,
      gps_point_count: gpsData.length,
      start_location: startGps ? `${startGps.lat.toFixed(6)}, ${startGps.lon.toFixed(6)}` : '-',
      end_location: endGps ? `${endGps.lat.toFixed(6)}, ${endGps.lon.toFixed(6)}` : '-',
      trend_data: trendData
    };
    reportRun.value = run;
    reportGps.value = gpsData;
    reportTelemetry.value = telemetryData;

    reportVisible.value = true;
    showToast('报告生成成功', 'success');

  } catch (e) {
    console.error('Generate report failed', e);
    if (isAuthError(e)) {
      showToast('生成报告失败：鉴权无效，请检查管理令牌', 'error');
    } else {
      showToast('生成报告失败，请重试', 'error');
    }
  } finally {
    reportLoading.value = false;
  }
};

// 导出 PDF（使用浏览器打印功能）
const handleExportPDF = async () => {
  if (exporting.value) {
    return;
  }
  if (!reportData.value) {
    showToast('暂无报告数据', 'warning');
    return;
  }
  exporting.value = true;
  try {
    if (!reportRun.value) {
      showToast('暂无报告任务', 'warning');
      return;
    }
    showToast('正在生成 PDF...', 'info');
    const response = await http.get(`/runs/${reportRun.value.run_id}/report.pdf`, {
      responseType: 'blob',
      timeout: 60000
    });
    const blob = new Blob([response.data], { type: 'application/pdf' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const safeName = (reportData.value.run_name || 'report').replace(/[\\/:*?"<>|]/g, '-');
    link.href = url;
    link.download = `${safeName}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    showToast('PDF 导出成功', 'success', 2000);
  } catch (e) {
    console.error('Export PDF failed', e);
    if (isAuthError(e)) {
      showToast('PDF 导出失败：鉴权无效，请检查管理令牌', 'error');
    } else {
      showToast('PDF 导出失败，请重试', 'error');
    }
  } finally {
    exporting.value = false;
  }
};

// 导出 Excel（复用现有的导出功能）
const handleExportExcel = async () => {
  if (!reportRun.value) {
    showToast('暂无报告数据', 'warning');
    return;
  }
  await exportRunData(reportRun.value, reportGps.value, reportTelemetry.value);
};

// 导出 Excel 功能
const exportRunData = async (
  run: RunSummary,
  cachedGps?: GpsPoint[],
  cachedTelemetry?: any[]
) => {
  if (exporting.value) return;
  exporting.value = true;

  try {
    showToast('正在获取数据...', 'info');

    // 分别获取 GPS 和 Telemetry 数据，避免一个失败导致全部失败
    let gpsData: any[] = cachedGps ? [...cachedGps] : [];
    let telemetryData: any[] = cachedTelemetry ? [...cachedTelemetry] : [];

    try {
      if (!cachedGps) {
        const gpsResponse = await http.get(`/runs/${run.run_id}/gps`, { params: { limit: 100000 } });
        gpsData = gpsResponse.data || [];
      }
    } catch (e) {
      console.error('获取GPS数据失败', e);
    }

    try {
      if (!cachedTelemetry) {
        const telemetryResponse = await http.get(`/runs/${run.run_id}/telemetry`, { params: { bucket: '1s' } });
        telemetryData = telemetryResponse.data || [];
      }
    } catch (e) {
      console.error('获取播种数据失败', e);
    }

    console.log('GPS数据条数:', gpsData.length);
    console.log('播种数据条数:', telemetryData.length);

    if (gpsData.length === 0 && telemetryData.length === 0) {
      showToast('该记录暂无数据', 'warning');
      return;
    }

    // 创建工作簿
    const wb = XLSX.utils.book_new();

    // GPS 数据表
    if (gpsData.length > 0) {
      const gpsSheet = gpsData.map((item: any) => ({
        '时间': new Date(item.ts).toLocaleString('zh-CN'),
        '经度': item.lon,
        '纬度': item.lat
      }));
      const ws1 = XLSX.utils.json_to_sheet(gpsSheet);
      XLSX.utils.book_append_sheet(wb, ws1, 'GPS数据');
    }

    // 播种数据表
    if (telemetryData.length > 0) {
      const telemetrySheet = telemetryData.map((item: any) => {
        // 匀播指数 = 总播种量 / 总里程
        const total = item.seed_total_g || 0;
        const distance = item.distance_m || 0;
        const uniformityIndex = distance > 0 && total > 0 ? total / distance : 0;

        return {
          '时间': new Date(item.ts).toLocaleString('zh-CN'),
          '通道1(g)': item.channel1_g?.toFixed(2) || '',
          '通道2(g)': item.channel2_g?.toFixed(2) || '',
          '通道3(g)': item.channel3_g?.toFixed(2) || '',
          '通道4(g)': item.channel4_g?.toFixed(2) || '',
          '通道5(g)': item.channel5_g?.toFixed(2) || '',
          '总播种量(g)': item.seed_total_g?.toFixed(2) || '',
          '作业里程(m)': item.distance_m?.toFixed(2) || '',
          '漏播里程(m)': item.leak_distance_m?.toFixed(2) || '',
          '作业速度(km/h)': item.speed_kmh?.toFixed(2) || '',
          '匀播指数(g/m)': uniformityIndex.toFixed(2),
          '通道1警报': item.alarm_channel1 ? '是' : '否',
          '通道2警报': item.alarm_channel2 ? '是' : '否',
          '通道3警报': item.alarm_channel3 ? '是' : '否',
          '通道4警报': item.alarm_channel4 ? '是' : '否',
          '通道5警报': item.alarm_channel5 ? '是' : '否',
          '堵塞告警': item.alarm_blocked ? '是' : '否',
          '缺种告警': item.alarm_no_seed ? '是' : '否'
        };
      });
      const ws2 = XLSX.utils.json_to_sheet(telemetrySheet);
      XLSX.utils.book_append_sheet(wb, ws2, '播种数据');
    }

    // 生成文件名：run-时间.xlsx
    const startTime = new Date(run.started_at);
    const fileName = `run-${startTime.getFullYear()}${String(startTime.getMonth() + 1).padStart(2, '0')}${String(startTime.getDate()).padStart(2, '0')}-${String(startTime.getHours()).padStart(2, '0')}${String(startTime.getMinutes()).padStart(2, '0')}${String(startTime.getSeconds()).padStart(2, '0')}.xlsx`;

    // 导出文件
    XLSX.writeFile(wb, fileName);
    showToast(`导出成功：${fileName}`, 'success', 3000);

  } catch (e) {
    console.error('Export failed', e);
    if (isAuthError(e)) {
      showToast('导出失败：鉴权无效，请检查管理令牌', 'error');
    } else {
      showToast('导出失败，请重试', 'error');
    }
  } finally {
    exporting.value = false;
  }
};

onMounted(async () => { initMap(); await loadRuns(); });

onBeforeUnmount(() => {
  if (toastTimer) {
    window.clearTimeout(toastTimer);
    toastTimer = null;
  }
  if (mapInstance) {
    try {
      mapInstance.clearOverlays();
    } catch {
      // ignore map cleanup errors on unmount
    }
    mapInstance = null;
    overlay = null;
  }
});
</script>

<style scoped>
.history-container { padding: 16px; width: 100%; min-height: 100vh; margin: 0; font-family: var(--font-main); color: var(--c-text-primary); }
.history-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid var(--c-border); padding-bottom: 12px; gap: 12px; }
.title-wrap h2 { margin: 0; font-size: 26px; color: var(--c-text-primary); font-weight: 800; }
.title-wrap p { margin: 3px 0 0; color: var(--c-text-secondary); font-size: 13px; }
.back-btn { padding: 9px 15px; border: 1px solid #93b2dd; background: #f8fbff; cursor: pointer; border-radius: 999px; font-size: 14px; color: #1e3a8a; font-weight: 700; white-space: nowrap; }
.back-btn:hover { background: #eaf2ff; }
.history-body { display: grid; grid-template-columns: 320px 1fr; gap: 12px; min-height: calc(100vh - 132px); }
.runs-list { border: 1px solid var(--c-border); padding: 10px; max-height: calc(100vh - 132px); overflow: auto; border-radius: 12px; background: #ffffff; box-shadow: var(--shadow-sm); }
.list-title { font-weight: 800; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid var(--c-border); color: var(--c-text-primary); }
.list-tools { display: grid; grid-template-columns: 1fr; gap: 8px; margin-bottom: 10px; }
.tool-input, .tool-select { width: 100%; border: 1px solid #c7d8ea; border-radius: 8px; padding: 8px 10px; font-size: 13px; color: var(--c-text-primary); background: #fff; }
.tool-refresh { border: 1px solid #a8bfd8; border-radius: 8px; background: #eef4ff; padding: 8px 10px; cursor: pointer; font-size: 13px; color: #1e3a8a; font-weight: 700; }
.tool-refresh:disabled { opacity: 0.6; cursor: not-allowed; }
.loading { text-align: center; padding: 20px; color: var(--c-text-primary); }
.load-error { display: flex; flex-direction: column; gap: 8px; border: 1px solid #ffd6d6; background: #fff5f5; color: #7f1d1d; border-radius: 8px; padding: 10px; font-size: 12px; margin-bottom: 8px; }
.runs-list ul { list-style: none; padding: 0; margin: 0; }
.runs-list li { padding: 10px; border: 1px solid #e6edf5; border-radius: 10px; margin-bottom: 8px; display: flex; flex-direction: column; gap: 8px; background: #fff; }
.run-item { cursor: pointer; flex: 1; text-align: left; width: 100%; border: 0; background: transparent; padding: 0; color: inherit; }
.runs-list li:hover .run-item { background: #f2f7fd; padding: 6px; border-radius: 6px; }
.runs-list li.active { background: #edf3ff; border-color: #8cb4df; box-shadow: inset 0 0 0 1px #c5dbf1; }
.runs-list li.empty { color: var(--c-text-secondary); text-align: center; cursor: default; }
.run-name { font-weight: 700; font-size: 14px; margin-bottom: 4px; color: var(--c-text-primary); line-height: 1.4; }
.run-time { font-size: 12px; color: var(--c-text-secondary); }
.action-buttons { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.action-btn {
  padding: 7px 8px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
  font-weight: 700;
}
.action-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.report-btn { background: #16a34a; color: white; }
.report-btn:hover { filter: brightness(1.08); }
.export-btn { background: #1d4ed8; color: white; }
.export-btn:hover:not(:disabled) { filter: brightness(1.08); }
.export-btn:disabled { background: #d9d9d9; cursor: not-allowed; }
.delete-btn { background: #dc2626; color: white; }
.delete-btn:hover { filter: brightness(1.08); }
.map-section { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.run-info { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; font-size: 13px; padding: 10px; background: #fff; border-radius: 10px; flex-wrap: wrap; color: var(--c-text-primary); border: 1px solid var(--c-border); box-shadow: var(--shadow-sm); }
.run-info > div { background: #f8fbff; border: 1px solid #dde8f4; border-radius: 8px; padding: 8px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.map-frame { flex: 1; border: 1px solid var(--c-border-strong); min-height: 500px; border-radius: 12px; overflow: hidden; position: relative; background: var(--c-bg-panel); box-shadow: var(--shadow-md); }
#history-map { width: 100%; height: 100%; min-height: 500px; }
.map-loading { position: absolute; top: 10px; left: 10px; z-index: 1000; background: rgba(255,255,255,0.95); border: 1px solid #d0d7e2; border-radius: 8px; padding: 8px 10px; font-size: 12px; color: #1f2937; }
.map-empty { position: absolute; top: 10px; left: 10px; z-index: 1000; background: rgba(255,255,255,0.95); border: 1px solid var(--c-border); border-radius: 8px; padding: 8px 10px; font-size: 12px; color: var(--c-text-secondary); }
.map-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 999;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.map-ctrl-btn {
  width: 34px;
  height: 34px;
  border: 1px solid #9bb1c8;
  background: rgba(255, 255, 255, 0.96);
  border-radius: 8px;
  font-size: 18px;
  font-weight: bold;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
}
.map-ctrl-btn:hover { background: #edf5ff; }

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
  .history-container { padding: 10px; }
  .history-header { flex-direction: column; align-items: stretch; }
  .title-wrap h2 { font-size: 20px; }
  .history-body { grid-template-columns: 1fr; min-height: auto; }
  .runs-list { max-height: 260px; }
  .run-info { flex-direction: column; gap: 5px; }
  .run-info { grid-template-columns: 1fr; }
  .map-frame { min-height: 400px; }
  #history-map { min-height: 400px; }
  .toast { top: 60px; min-width: 150px; max-width: 90%; font-size: 12px; padding: 10px 16px; }
}
</style>
