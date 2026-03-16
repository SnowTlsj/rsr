<template>
  <div class="report-modal" v-if="visible" @click.self="close">
    <div class="report-content">
      <div class="report-header">
        <h2>播种报告</h2>
        <button class="close-btn" @click="close">✕</button>
      </div>
      
      <div class="report-body" ref="reportBody">
        <section class="report-section">
          <h3>任务信息</h3>
          <div class="info-grid">
            <div class="info-item"><span class="label">任务名称：</span><span class="value">{{ report.run_name }}</span></div>
            <div class="info-item"><span class="label">开始时间：</span><span class="value">{{ formatTime(report.started_at) }}</span></div>
            <div class="info-item"><span class="label">结束时间：</span><span class="value">{{ formatTime(report.ended_at) }}</span></div>
            <div class="info-item"><span class="label">作业时长：</span><span class="value">{{ report.duration }}</span></div>
          </div>
        </section>

        <section class="report-section">
          <h3>播种统计</h3>
          <div class="stats-grid">
            <div class="stat-card highlight"><div class="stat-label">总播种量</div><div class="stat-value">{{ report.total_seed_kg }} kg</div></div>
            <div class="stat-card"><div class="stat-label">作业里程</div><div class="stat-value">{{ report.total_distance_km }} km</div></div>
            <div class="stat-card"><div class="stat-label">漏播里程</div><div class="stat-value">{{ report.leak_distance_km }} km</div></div>
            <div class="stat-card"><div class="stat-label">平均速度</div><div class="stat-value">{{ report.avg_speed_kmh }} km/h</div></div>
            <div class="stat-card highlight"><div class="stat-label">匀播指数</div><div class="stat-value">{{ report.uniformity_index }} g/m</div></div>
          </div>
          <div class="channel-stats">
            <h4>各通道播种量</h4>
            <div class="channel-grid">
              <div class="channel-item" v-for="i in 5" :key="i">
                <span class="channel-label">通道{{ i }}：</span>
                <span class="channel-value">{{ report[`channel${i}_kg`] }} kg</span>
              </div>
            </div>
          </div>
        </section>

        <section class="report-section">
          <h3>告警统计</h3>
          <div class="alarm-grid">
            <div class="alarm-item"><span class="alarm-icon warning-icon"></span><span class="alarm-label">堵塞告警：</span><span class="alarm-value">{{ report.alarm_blocked_count }} 次</span></div>
            <div class="alarm-item"><span class="alarm-icon warning-icon"></span><span class="alarm-label">缺种告警：</span><span class="alarm-value">{{ report.alarm_no_seed_count }} 次</span></div>
          </div>
        </section>

        <section class="report-section">
          <h3>GPS 轨迹</h3>
          <div class="gps-stats">
            <div class="gps-item"><span class="label">轨迹点数量：</span><span class="value">{{ report.gps_point_count }} 个</span></div>
            <div class="gps-item"><span class="label">起始位置：</span><span class="value">{{ report.start_location }}</span></div>
            <div class="gps-item"><span class="label">结束位置：</span><span class="value">{{ report.end_location }}</span></div>
          </div>
          <div v-if="report.map_preview_url" class="map-preview">
            <img :src="report.map_preview_url" alt="GPS轨迹静态地图预览" />
          </div>
        </section>

        <section class="report-section">
          <h3>播种量趋势</h3>
          <div ref="chartContainer" class="chart-container"></div>
        </section>
      </div>

      <div class="report-footer">
        <button class="btn-secondary" @click="close">关闭</button>
        <button class="btn-primary" @click="exportPDF" :disabled="isExporting">{{ isExporting ? '导出中...' : '导出PDF' }}</button>
        <button class="btn-primary" @click="exportExcel" :disabled="isExporting">{{ isExporting ? '导出中...' : '导出Excel' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick, onBeforeUnmount } from 'vue';
import * as echarts from 'echarts';
import type { ReportData } from '@/types/history';

const props = defineProps<{ visible: boolean; report: ReportData; exporting?: boolean }>();
const emit = defineEmits<{ (e: 'close'): void; (e: 'export-pdf'): void; (e: 'export-excel'): void; }>();

const reportBody = ref<HTMLElement | null>(null);
const chartContainer = ref<HTMLElement | null>(null);
let chartInstance: any = null;
let resizeHandler: (() => void) | null = null;
const isExporting = computed(() => !!props.exporting);

const formatTime = (value: string) => { if (!value) return '-'; return new Date(value).toLocaleString('zh-CN'); };
const close = () => { emit('close'); };
const exportPDF = () => { emit('export-pdf'); };
const exportExcel = () => { emit('export-excel'); };

const initChart = () => {
  if (!chartContainer.value || !props.report.trend_data) return;
  if (chartInstance) { chartInstance.dispose(); }
  chartInstance = echarts.init(chartContainer.value);
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['通道1', '通道2', '通道3', '通道4', '通道5'] },
    xAxis: { type: 'category', data: props.report.trend_data.map((d: any) => d.time) },
    yAxis: { type: 'value', name: '播种量 (g)' },
    series: [
      { name: '通道1', type: 'line', data: props.report.trend_data.map((d: any) => d.channel1) },
      { name: '通道2', type: 'line', data: props.report.trend_data.map((d: any) => d.channel2) },
      { name: '通道3', type: 'line', data: props.report.trend_data.map((d: any) => d.channel3) },
      { name: '通道4', type: 'line', data: props.report.trend_data.map((d: any) => d.channel4) },
      { name: '通道5', type: 'line', data: props.report.trend_data.map((d: any) => d.channel5) }
    ]
  };
  chartInstance.setOption(option);
  resizeHandler = () => chartInstance?.resize();
  window.addEventListener('resize', resizeHandler);
};

watch(() => props.visible, async (newVal) => {
  if (newVal) {
    await nextTick();
    initChart();
    return;
  }
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler);
    resizeHandler = null;
  }
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});

onBeforeUnmount(() => {
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler);
    resizeHandler = null;
  }
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>

<style scoped>
.report-modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.6); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 20px; }
.report-content { background: var(--c-bg-panel); border-radius: 8px; width: 100%; max-width: 900px; max-height: 90vh; display: flex; flex-direction: column; box-shadow: var(--shadow-md); }
.report-header { display: flex; justify-content: space-between; align-items: center; padding: 20px; border-bottom: 1px solid var(--c-border); }
.report-header h2 { margin: 0; font-size: 24px; color: var(--c-text-primary); font-weight: bold; }
.close-btn { background: none; border: none; font-size: 24px; cursor: pointer; color: #666; padding: 0; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: 4px; }
.close-btn:hover { background: var(--c-bg-hover); color: var(--c-text-primary); }
.report-body { flex: 1; overflow-y: auto; padding: 20px; }
.report-section { margin-bottom: 30px; }
.report-section h3 { font-size: 18px; color: var(--c-text-primary); font-weight: bold; margin: 0 0 15px 0; padding-bottom: 8px; border-bottom: 2px solid var(--c-primary); }
.report-section h4 { font-size: 16px; color: var(--c-text-primary); font-weight: 600; margin: 20px 0 10px 0; }
.info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; }
.info-item { display: flex; padding: 8px; background: var(--c-bg-muted); border-radius: 4px; }
.info-item .label { font-weight: 500; color: var(--c-text-primary); min-width: 100px; }
.info-item .value { color: var(--c-text-primary); }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
.stat-card { background: var(--c-bg-muted); padding: 20px; border-radius: 8px; text-align: center; border: 1px solid var(--c-border); }
.stat-card.highlight { background: var(--c-primary-soft); border-color: var(--c-primary); }
.stat-label { font-size: 14px; color: var(--c-text-primary); margin-bottom: 8px; }
.stat-value { font-size: 24px; font-weight: bold; color: var(--c-text-primary); }
.channel-stats { background: var(--c-bg-muted); padding: 15px; border-radius: 8px; }
.channel-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-top: 10px; }
.channel-item { display: flex; justify-content: space-between; padding: 8px 12px; background: white; border-radius: 4px; border: 1px solid var(--c-border); }
.channel-label { font-weight: 500; color: var(--c-text-primary); }
.channel-value { font-weight: bold; color: var(--c-primary); }
.alarm-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }
.alarm-item { display: flex; align-items: center; gap: 10px; padding: 15px; background: #fff3e0; border-radius: 8px; border: 2px solid #ffb74d; }
.alarm-icon { font-size: 24px; }
.alarm-icon.warning-icon { width: 24px; height: 24px; background: #f57c00; border-radius: 50%; position: relative; }
.alarm-icon.warning-icon::before { content: '!'; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: white; font-weight: bold; font-size: 16px; }
.alarm-label { font-weight: 500; color: var(--c-text-primary); }
.alarm-value { font-weight: bold; color: #f57c00; margin-left: auto; }
.gps-stats { display: flex; flex-direction: column; gap: 10px; }
.gps-item { display: flex; padding: 10px; background: var(--c-bg-muted); border-radius: 4px; }
.gps-item .label { font-weight: 500; color: var(--c-text-primary); min-width: 120px; }
.gps-item .value { color: var(--c-text-primary); }
.map-preview { margin-top: 14px; border: 1px solid var(--c-border); border-radius: 10px; overflow: hidden; background: #fff; }
.map-preview img { display: block; width: 100%; height: auto; }
.chart-container { width: 100%; height: 300px; background: var(--c-bg-muted); border-radius: 8px; border: 1px solid var(--c-border); }
.report-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 20px; border-top: 1px solid var(--c-border); }
.btn-primary, .btn-secondary { padding: 10px 20px; border: none; border-radius: 4px; font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.2s; }
.btn-primary { background: var(--c-primary); color: white; }
.btn-primary:hover:not(:disabled) { filter: brightness(1.05); }
.btn-primary:disabled { background: #d9d9d9; cursor: not-allowed; }
.btn-secondary { background: var(--c-bg-muted); color: var(--c-text-primary); border: 1px solid var(--c-border); }
.btn-secondary:hover { background: var(--c-bg-hover); }
</style>
