import { ref } from 'vue';
import * as XLSX from 'xlsx';
import { http } from '@/api/http';
import type { GpsPoint, ReportData, RunSummary } from '@/types/history';
import { extractErrorMessage, isAuthError } from '@/utils/httpError';

interface ToastApi {
  success: (message: string, duration?: number) => void;
  error: (message: string, duration?: number) => void;
  warning: (message: string, duration?: number) => void;
  info: (message: string, duration?: number) => void;
}

const EMPTY_REPORT: ReportData = {
  run_id: '',
  run_name: '',
  started_at: '',
  ended_at: '',
  duration: '',
  total_seed_kg: '0',
  total_distance_km: '0',
  leak_distance_km: '0',
  avg_speed_kmh: '0',
  uniformity_index: '0',
  channel1_kg: '0',
  channel2_kg: '0',
  channel3_kg: '0',
  channel4_kg: '0',
  channel5_kg: '0',
  alarm_blocked_count: 0,
  alarm_no_seed_count: 0,
  gps_point_count: 0,
  start_location: '-',
  end_location: '-',
  map_preview_url: '',
  trend_data: []
};

export function useHistoryReports(toast: ToastApi) {
  const exporting = ref(false);
  const reportLoading = ref(false);
  const reportVisible = ref(false);
  const reportRun = ref<RunSummary | null>(null);
  const reportData = ref<ReportData>({ ...EMPTY_REPORT });
  const baiduAk = (import.meta.env.VITE_BAIDU_AK || '').trim();

  const resolveRequestErrorMessage = (requestError: unknown, fallback: string) => {
    if (isAuthError(requestError)) {
      return '管理会话已失效，请重新登录';
    }
    return extractErrorMessage(requestError, fallback);
  };

  const buildStaticMapUrl = (gpsData: GpsPoint[]) => {
    if (!baiduAk || gpsData.length === 0) {
      return '';
    }
    const stride = Math.max(Math.ceil(gpsData.length / 80), 1);
    const sampled = gpsData.filter((_, index) => index % stride === 0);
    const path = sampled.map((point) => `${point.lon},${point.lat}`).join(';');
    const start = gpsData[0];
    const end = gpsData[gpsData.length - 1];
    const centerLon = ((start.lon + end.lon) / 2).toFixed(6);
    const centerLat = ((start.lat + end.lat) / 2).toFixed(6);
    const params = new URLSearchParams({
      ak: baiduAk,
      width: '960',
      height: '360',
      center: `${centerLon},${centerLat}`,
      zoom: '15',
      scale: '2',
      paths: path,
      pathStyles: '0x2563eb,6,0.9',
      markers: `${start.lon},${start.lat}|${end.lon},${end.lat}`,
      markerStyles: 'l,A,0x16a34a|l,B,0xdc2626'
    });
    return `https://api.map.baidu.com/staticimage/v2?${params.toString()}`;
  };

  const buildReportData = (run: RunSummary, gpsData: GpsPoint[], telemetryData: Record<string, any>[]): ReportData => {
    const duration = run.ended_at
      ? Math.round((new Date(run.ended_at).getTime() - new Date(run.started_at).getTime()) / 1000 / 60)
      : 0;
    const lastTelemetry = telemetryData.length > 0 ? telemetryData[telemetryData.length - 1] : null;

    let alarmBlocked = 0;
    let alarmNoSeed = 0;
    telemetryData.forEach((item: any) => {
      if (item.alarm_channel1 || item.alarm_channel2 || item.alarm_channel3 || item.alarm_channel4 || item.alarm_channel5) {
        alarmBlocked += 1;
      }
      if (item.alarm_blocked) alarmBlocked += 1;
      if (item.alarm_no_seed) alarmNoSeed += 1;
    });

    const startGps = gpsData.length > 0 ? gpsData[0] : null;
    const endGps = gpsData.length > 0 ? gpsData[gpsData.length - 1] : null;
    const sampleRate = Math.max(1, Math.floor(telemetryData.length / 100));
    const trendData = telemetryData
      .filter((_, index) => index % sampleRate === 0)
      .map((item: any) => ({
        time: new Date(item.ts).toLocaleTimeString('zh-CN'),
        channel1: item.channel1_g || 0,
        channel2: item.channel2_g || 0,
        channel3: item.channel3_g || 0,
        channel4: item.channel4_g || 0,
        channel5: item.channel5_g || 0
      }));

    let uniformityIndex = '0.00';
    if (lastTelemetry) {
      const total = lastTelemetry.seed_total_g || 0;
      const distance = lastTelemetry.distance_m || 0;
      if (distance > 0 && total > 0) {
        uniformityIndex = (total / distance).toFixed(2);
      }
    }

    return {
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
      map_preview_url: buildStaticMapUrl(gpsData),
      trend_data: trendData
    };
  };

  const showReport = async (run: RunSummary) => {
    if (reportLoading.value) return;
    reportLoading.value = true;
    try {
      toast.info('正在生成报告...');
      const [gpsResponse, telemetryResponse] = await Promise.all([
        http.get(`/runs/${run.run_id}/gps`, { params: { limit: 100000 } }),
        http.get(`/runs/${run.run_id}/telemetry`, { params: { bucket: '5s' } })
      ]);
      reportRun.value = run;
      reportData.value = buildReportData(run, gpsResponse.data || [], telemetryResponse.data || []);
      reportVisible.value = true;
      toast.success('报告生成成功');
    } catch (requestError) {
      toast.error(resolveRequestErrorMessage(requestError, '生成报告失败，请重试'));
    } finally {
      reportLoading.value = false;
    }
  };

  const exportRunData = async (run: RunSummary, cachedGps?: GpsPoint[], cachedTelemetry?: Record<string, any>[]) => {
    if (exporting.value) return;
    exporting.value = true;

    try {
      toast.info('正在获取数据...');
      let gpsData = cachedGps ? [...cachedGps] : [];
      let telemetryData = cachedTelemetry ? [...cachedTelemetry] : [];

      if (!cachedGps) {
        try {
          const gpsResponse = await http.get(`/runs/${run.run_id}/gps`, { params: { limit: 100000 } });
          gpsData = gpsResponse.data || [];
        } catch (requestError) {
          console.error('获取GPS数据失败', requestError);
        }
      }

      if (!cachedTelemetry) {
        try {
          const telemetryResponse = await http.get(`/runs/${run.run_id}/telemetry`, { params: { bucket: '5s' } });
          telemetryData = telemetryResponse.data || [];
        } catch (requestError) {
          console.error('获取播种数据失败', requestError);
        }
      }

      if (gpsData.length === 0 && telemetryData.length === 0) {
        toast.warning('该记录暂无数据');
        return;
      }

      const workbook = XLSX.utils.book_new();

      if (gpsData.length > 0) {
        const gpsSheet = gpsData.map((item) => ({
          '时间': new Date(item.ts).toLocaleString('zh-CN'),
          '经度': item.lon,
          '纬度': item.lat
        }));
        XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(gpsSheet), 'GPS数据');
      }

      if (telemetryData.length > 0) {
        const telemetrySheet = telemetryData.map((item: any) => {
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
        XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(telemetrySheet), '播种数据');
      }

      const startTime = new Date(run.started_at);
      const fileName = `run-${startTime.getFullYear()}${String(startTime.getMonth() + 1).padStart(2, '0')}${String(startTime.getDate()).padStart(2, '0')}-${String(startTime.getHours()).padStart(2, '0')}${String(startTime.getMinutes()).padStart(2, '0')}${String(startTime.getSeconds()).padStart(2, '0')}.xlsx`;
      XLSX.writeFile(workbook, fileName);
      toast.success(`导出成功：${fileName}`, 3000);
    } catch (requestError) {
      toast.error(resolveRequestErrorMessage(requestError, '导出失败，请重试'));
    } finally {
      exporting.value = false;
    }
  };

  const handleExportPDF = async () => {
    if (exporting.value) return;
    if (!reportRun.value) {
      toast.warning('暂无报告任务');
      return;
    }

    exporting.value = true;
    try {
      toast.info('正在生成 PDF...');
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
      toast.success('PDF 导出成功', 2000);
    } catch (requestError) {
      toast.error(resolveRequestErrorMessage(requestError, 'PDF 导出失败，请重试'));
    } finally {
      exporting.value = false;
    }
  };

  const handleExportExcel = async () => {
    if (!reportRun.value) {
      toast.warning('暂无报告数据');
      return;
    }
    await exportRunData(reportRun.value);
  };

  return {
    exporting,
    reportLoading,
    reportVisible,
    reportData,
    showReport,
    exportRunData,
    handleExportPDF,
    handleExportExcel
  };
}
