<template>
  <div class="history-container">
    <header class="history-header">
      <h2>历史播种数据</h2>
      <button class="back-btn" @click="goBack">返回监控</button>
    </header>

    <div class="history-body">
      <aside class="runs-list">
        <div class="list-title">播种记录 (最近30天)</div>
        <div v-if="loading" class="loading">加载中...</div>
        <ul v-else>
          <li v-for="run in runs" :key="run.run_id" :class="{ active: run.run_id === selectedRunId }">
            <div @click="selectRun(run.run_id)" class="run-item">
              <div class="run-name">{{ run.run_name }}</div>
              <div class="run-time">{{ formatTime(run.started_at) }}</div>
            </div>
            <div class="action-buttons">
              <button
                class="action-btn report-btn"
                @click.stop="showReport(run)"
                title="查看报告"
              >
                报告
              </button>
              <button
                class="action-btn export-btn"
                @click.stop="exportRunData(run)"
                :disabled="exporting"
                title="导出Excel"
              >
                {{ exporting ? '导出中...' : '导出' }}
              </button>
              <button
                class="action-btn delete-btn"
                @click.stop="deleteRun(run)"
                title="删除记录"
              >
                删除
              </button>
            </div>
          </li>
          <li v-if="runs.length === 0" class="empty">暂无记录</li>
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
          <div id="history-map"></div>
          <div class="map-controls">
            <button class="map-ctrl-btn" @click="zoomIn" title="放大">+</button>
            <button class="map-ctrl-btn" @click="zoomOut" title="缩小">-</button>
          </div>
        </div>
      </section>
    </div>

    <!-- 报告弹窗 -->
    <ReportModal
      :visible="reportVisible"
      :report="reportData"
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
import { onMounted, ref, reactive, computed } from 'vue';
import { useRouter } from 'vue-router';
import { http } from '@/api/http';
import * as XLSX from 'xlsx';
import ReportModal from '@/components/ReportModal.vue';

interface RunSummary {
  run_id: string;
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

interface TelemetryData {
  ts: string;
  channel1_g: number;
  channel2_g: number;
  channel3_g: number;
  channel4_g: number;
  channel5_g: number;
  seed_total_g: number;
  distance_m: number;
  leak_distance_m: number;
  speed_kmh: number;
  alarm_blocked: boolean;
  alarm_no_seed: boolean;
}

const router = useRouter();
const runs = ref<RunSummary[]>([]);
const selectedRunId = ref<string | null>(null);
const selectedRun = ref<RunSummary | null>(null);
const gpsPoints = ref<GpsPoint[]>([]);
const loading = ref(false);
const exporting = ref(false);

// 报告相关状态
const reportVisible = ref(false);
const reportData = ref<any>({
  machine_id: '', run_name: '', started_at: '', ended_at: '', duration: '',
  total_seed_kg: '0', total_distance_km: '0', leak_distance_km: '0', avg_speed_kmh: '0',
  channel1_kg: '0', channel2_kg: '0', channel3_kg: '0', channel4_kg: '0', channel5_kg: '0',
  alarm_blocked_count: 0, alarm_no_seed_count: 0, gps_point_count: 0,
  start_location: '-', end_location: '-', trend_data: []
});

let mapInstance: any = null;
let overlay: any = null;

const machineId = import.meta.env.VITE_MACHINE_ID || 'machine-001';

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
  try {
    const response = await http.get('/runs', { params: { days: 30, machine_id: machineId } });
    runs.value = (response.data || []).map((r: any) => ({ ...r, run_id: r.run_id || r.id }));
    if (runs.value.length === 0) {
      showToast('暂无历史记录', 'info');
    }
  } catch (e) {
    console.error('Load runs failed', e);
    showToast('加载历史记录失败，请重试', 'error');
  } finally {
    loading.value = false;
  }
};

const selectRun = async (runId: string) => {
  selectedRunId.value = runId;
  selectedRun.value = runs.value.find((run) => run.run_id === runId) || null;
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
    showToast('加载GPS轨迹失败，请重试', 'error');
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
      selectedRunId.value = '';
      selectedRun.value = null;
      gpsPoints.value = [];
      if (mapInstance) {
        mapInstance.clearOverlays();
      }
    }
  } catch (e) {
    console.error('Delete run failed', e);
    showToast('删除失败，请重试', 'error');
  }
};

const formatTime = (value: string) => new Date(value).toLocaleString('zh-CN');
const goBack = () => { router.push('/'); };

// 生成报告
const showReport = async (run: RunSummary) => {
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

    // 计算匀播指数
    let uniformityIndex = '0.0';
    if (lastTelemetry) {
      const channels = [
        lastTelemetry.channel1_g || 0,
        lastTelemetry.channel2_g || 0,
        lastTelemetry.channel3_g || 0,
        lastTelemetry.channel4_g || 0,
        lastTelemetry.channel5_g || 0
      ];
      const total = channels.reduce((sum, val) => sum + val, 0);
      const avg = total / 5;
      if (avg > 0) {
        const variance = channels.reduce((sum, val) => sum + Math.pow(val - avg, 2), 0) / 5;
        const stdDev = Math.sqrt(variance);
        const index = (1 - stdDev / avg) * 100;
        uniformityIndex = Math.max(0, Math.min(100, index)).toFixed(1);
      }
    }

    reportData.value = {
      machine_id: run.machine_id,
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

    reportVisible.value = true;
    showToast('报告生成成功', 'success');

  } catch (e) {
    console.error('Generate report failed', e);
    showToast('生成报告失败，请重试', 'error');
  }
};

// 导出 PDF（使用浏览器打印功能）
const handleExportPDF = () => {
  showToast('请使用浏览器打印功能保存为PDF', 'info', 3000);
  setTimeout(() => {
    window.print();
  }, 500);
};

// 导出 Excel（复用现有的导出功能）
const handleExportExcel = async () => {
  const run = runs.value.find(r => r.run_id === reportData.value.run_id);
  if (run) {
    await exportRunData(run);
  }
};

// 导出 Excel 功能
const exportRunData = async (run: RunSummary) => {
  if (exporting.value) return;
  exporting.value = true;

  try {
    showToast('正在获取数据...', 'info');

    // 分别获取 GPS 和 Telemetry 数据，避免一个失败导致全部失败
    let gpsData: any[] = [];
    let telemetryData: any[] = [];

    try {
      const gpsResponse = await http.get(`/runs/${run.run_id}/gps`, { params: { limit: 100000 } });
      gpsData = gpsResponse.data || [];
    } catch (e) {
      console.error('获取GPS数据失败', e);
    }

    try {
      const telemetryResponse = await http.get(`/runs/${run.run_id}/telemetry`, { params: { bucket: '1s' } });
      telemetryData = telemetryResponse.data || [];
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
        // 计算匀播指数
        const channels = [
          item.channel1_g || 0,
          item.channel2_g || 0,
          item.channel3_g || 0,
          item.channel4_g || 0,
          item.channel5_g || 0
        ];
        const total = channels.reduce((sum: number, val: number) => sum + val, 0);
        const avg = total / 5;
        let uniformityIndex = 0;
        if (avg > 0) {
          const variance = channels.reduce((sum: number, val: number) => sum + Math.pow(val - avg, 2), 0) / 5;
          const stdDev = Math.sqrt(variance);
          uniformityIndex = Math.max(0, Math.min(100, (1 - stdDev / avg) * 100));
        }

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
          '匀播指数(%)': uniformityIndex.toFixed(1),
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

    // 生成文件名：machineId-时间.xlsx
    const startTime = new Date(run.started_at);
    const fileName = `${run.machine_id}-${startTime.getFullYear()}${String(startTime.getMonth() + 1).padStart(2, '0')}${String(startTime.getDate()).padStart(2, '0')}-${String(startTime.getHours()).padStart(2, '0')}${String(startTime.getMinutes()).padStart(2, '0')}${String(startTime.getSeconds()).padStart(2, '0')}.xlsx`;

    // 导出文件
    XLSX.writeFile(wb, fileName);
    showToast(`导出成功：${fileName}`, 'success', 3000);

  } catch (e) {
    console.error('Export failed', e);
    showToast('导出失败，请重试', 'error');
  } finally {
    exporting.value = false;
  }
};

onMounted(async () => { initMap(); await loadRuns(); });
</script>

<style scoped>
.history-container { padding: 20px; max-width: 1400px; margin: 0 auto; font-family: "Microsoft YaHei", sans-serif; }
.history-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 2px solid #ccc; padding-bottom: 10px; }
.history-header h2 { margin: 0; font-size: 24px; color: #000; font-weight: bold; }
.back-btn { padding: 8px 16px; border: 1px solid #666; background: #f5f5f5; cursor: pointer; border-radius: 4px; font-size: 14px; }
.back-btn:hover { background: #e0e0e0; }
.history-body { display: flex; gap: 20px; }
.runs-list { width: 280px; border: 1px solid #ccc; padding: 10px; max-height: 700px; overflow: auto; border-radius: 4px; }
.list-title { font-weight: bold; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid #eee; color: #000; }
.loading { text-align: center; padding: 20px; color: #000; }
.runs-list ul { list-style: none; padding: 0; margin: 0; }
.runs-list li { padding: 10px; border-bottom: 1px solid #eee; border-radius: 4px; margin-bottom: 4px; display: flex; flex-direction: column; gap: 8px; }
.run-item { cursor: pointer; flex: 1; }
.runs-list li:hover .run-item { background: #f5f5f5; padding: 4px; border-radius: 4px; }
.runs-list li.active { background: #e6f2ff; border-color: #1d6fd8; }
.runs-list li.empty { color: #000; text-align: center; cursor: default; }
.run-name { font-weight: 600; font-size: 14px; margin-bottom: 4px; color: #000; }
.run-time { font-size: 12px; color: #000; }
.action-buttons { display: flex; gap: 8px; }
.action-btn {
  flex: 1;
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
  font-weight: 500;
}
.report-btn {
  background: #52c41a;
  color: white;
}
.report-btn:hover { background: #73d13d; }
.export-btn {
  background: #1890ff;
  color: white;
}
.export-btn:hover:not(:disabled) { background: #40a9ff; }
.export-btn:disabled { background: #d9d9d9; cursor: not-allowed; }
.delete-btn {
  background: #ff4d4f;
  color: white;
}
.delete-btn:hover { background: #ff7875; }
.map-section { flex: 1; display: flex; flex-direction: column; gap: 10px; }
.run-info { display: flex; gap: 20px; font-size: 14px; padding: 10px; background: #f9f9f9; border-radius: 4px; flex-wrap: wrap; color: #000; }
.map-frame { flex: 1; border: 2px solid #999; min-height: 500px; border-radius: 4px; overflow: hidden; position: relative; }
#history-map { width: 100%; height: 100%; min-height: 500px; }
.map-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 999;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.map-ctrl-btn {
  width: 32px;
  height: 32px;
  border: 1px solid #999;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 4px;
  font-size: 18px;
  font-weight: bold;
  cursor: pointer;
  box-shadow: 0 2px 5px rgba(0,0,0,0.3);
}
.map-ctrl-btn:hover { background: #e6e6e6; }

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
  .history-body { flex-direction: column; }
  .runs-list { width: 100%; max-height: 240px; }
  .run-info { flex-direction: column; gap: 5px; }
  .map-frame { min-height: 400px; }
  #history-map { min-height: 400px; }
  .toast { top: 60px; min-width: 150px; max-width: 90%; font-size: 12px; padding: 10px 16px; }
}
</style>
