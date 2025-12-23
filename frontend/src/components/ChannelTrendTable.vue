<template>
  <div class="trend-table">
    <table>
      <thead>
        <tr>
          <th>Channel</th>
          <th>Value (g)</th>
          <th>Trend (10 min)</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(value, index) in channels" :key="index">
          <td>Channel {{ index + 1 }}</td>
          <td>{{ value.toFixed(1) }}</td>
          <td>
            <div class="sparkline" :ref="setChartRef(index)"></div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch } from 'vue';
import * as echarts from 'echarts';
import type { ChannelPoint } from '@/stores/runStore';

const props = defineProps<{ channels: number[]; buffers: ChannelPoint[][] }>();

const chartRefs: HTMLDivElement[] = [];
const charts: echarts.ECharts[] = [];

const setChartRef = (index: number) => (el: Element | null) => {
  if (el && el instanceof HTMLDivElement) {
    chartRefs[index] = el;
  }
};

const buildSeries = (points: ChannelPoint[]) => {
  return points.map((point) => [point.ts, point.value]);
};

const renderChart = (index: number) => {
  const chart = charts[index];
  if (!chart) {
    return;
  }
  const points = props.buffers[index] || [];
  chart.setOption({
    xAxis: { type: 'time', show: false },
    yAxis: { type: 'value', show: false },
    grid: { left: 0, right: 0, top: 4, bottom: 4 },
    series: [
      {
        type: 'line',
        data: buildSeries(points),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, color: '#1d6fd8' },
        areaStyle: { opacity: 0.15, color: '#1d6fd8' }
      }
    ]
  });
};

onMounted(() => {
  chartRefs.forEach((el, index) => {
    if (!el) {
      return;
    }
    const chart = echarts.init(el);
    charts[index] = chart;
    renderChart(index);
  });
});

watch(
  () => props.buffers,
  () => {
    for (let i = 0; i < charts.length; i += 1) {
      renderChart(i);
    }
  },
  { deep: true }
);

onBeforeUnmount(() => {
  charts.forEach((chart) => chart.dispose());
});
</script>

<style scoped>
.trend-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.trend-table th,
.trend-table td {
  border: 1px solid #d0d0d0;
  padding: 6px 8px;
  text-align: center;
}

.sparkline {
  width: 180px;
  height: 60px;
}
</style>
