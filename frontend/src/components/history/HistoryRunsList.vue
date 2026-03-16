<template>
  <aside class="runs-list">
    <div class="list-title">播种记录 (最近30天)</div>
    <div class="list-tools">
      <input
        :value="keyword"
        class="tool-input"
        placeholder="搜索任务名称"
        aria-label="搜索任务名称"
        @input="emit('update:keyword', ($event.target as HTMLInputElement).value)"
      />
      <select
        :value="sortMode"
        class="tool-select"
        aria-label="排序方式"
        @change="emit('update:sortMode', ($event.target as HTMLSelectElement).value)"
      >
        <option value="time_desc">时间倒序</option>
        <option value="time_asc">时间正序</option>
        <option value="name_asc">名称 A-Z</option>
        <option value="name_desc">名称 Z-A</option>
      </select>
      <button class="tool-refresh" type="button" :disabled="loading" @click="emit('refresh')">
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <StateBlock
      v-if="loading"
      title="加载中..."
      description="正在获取最近 30 天的播种记录。"
      variant="loading"
    />
    <StateBlock
      v-else-if="loadError"
      title="加载失败"
      :description="loadError"
      action-label="重试"
      variant="error"
      @action="emit('refresh')"
    />
    <ul v-else-if="runs.length > 0">
      <li v-for="run in runs" :key="run.run_id" :class="{ active: run.run_id === selectedRunId }">
        <button type="button" class="run-item" :aria-label="`查看任务 ${run.run_name}`" @click="emit('select', run.run_id)">
          <div class="run-name">{{ run.run_name }}</div>
          <div class="run-time">{{ formatTime(run.started_at) }}</div>
        </button>
        <div class="action-buttons">
          <button class="action-btn report-btn" type="button" :disabled="reportLoading || exporting" title="查看报告" @click.stop="emit('report', run)">
            {{ reportLoading ? '生成中...' : '报告' }}
          </button>
          <button class="action-btn export-btn" type="button" :disabled="exporting" title="导出Excel" @click.stop="emit('export', run)">
            {{ exporting ? '导出中...' : '导出' }}
          </button>
          <button class="action-btn delete-btn" type="button" :disabled="reportLoading || exporting" title="删除记录" @click.stop="emit('delete', run)">
            删除
          </button>
        </div>
      </li>
    </ul>
    <StateBlock
      v-else
      title="暂无记录"
      description="最近 30 天内还没有播种任务，开始一次播种后会出现在这里。"
      variant="empty"
    />
  </aside>
</template>

<script setup lang="ts">
import StateBlock from '@/components/StateBlock.vue';
import type { RunSummary } from '@/types/history';

defineProps<{
  runs: RunSummary[];
  selectedRunId: string | null;
  loading: boolean;
  loadError: string;
  keyword: string;
  sortMode: string;
  reportLoading: boolean;
  exporting: boolean;
}>();

const emit = defineEmits<{
  'update:keyword': [value: string];
  'update:sortMode': [value: string];
  refresh: [];
  select: [runId: string];
  report: [run: RunSummary];
  export: [run: RunSummary];
  delete: [run: RunSummary];
}>();

const formatTime = (value: string) => new Date(value).toLocaleString('zh-CN');
</script>

<style scoped>
.runs-list { border: 1px solid var(--c-border); padding: 10px; max-height: calc(100vh - 132px); overflow: auto; border-radius: 12px; background: #ffffff; box-shadow: var(--shadow-sm); }
.list-title { font-weight: 800; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid var(--c-border); color: var(--c-text-primary); }
.list-tools { display: grid; grid-template-columns: 1fr; gap: 8px; margin-bottom: 10px; }
.tool-input, .tool-select { width: 100%; border: 1px solid #c7d8ea; border-radius: 8px; padding: 8px 10px; font-size: 13px; color: var(--c-text-primary); background: #fff; }
.tool-refresh { border: 1px solid #a8bfd8; border-radius: 8px; background: #eef4ff; padding: 8px 10px; cursor: pointer; font-size: 13px; color: #1e3a8a; font-weight: 700; }
.tool-refresh:disabled { opacity: 0.6; cursor: not-allowed; }
.runs-list ul { list-style: none; padding: 0; margin: 0; }
.runs-list li { padding: 10px; border: 1px solid #e6edf5; border-radius: 10px; margin-bottom: 8px; display: flex; flex-direction: column; gap: 8px; background: #fff; }
.run-item { cursor: pointer; flex: 1; text-align: left; width: 100%; border: 0; background: transparent; padding: 0; color: inherit; }
.runs-list li:hover .run-item { background: #f2f7fd; padding: 6px; border-radius: 6px; }
.runs-list li.active { background: #edf3ff; border-color: #8cb4df; box-shadow: inset 0 0 0 1px #c5dbf1; }
.run-name { font-weight: 700; font-size: 14px; margin-bottom: 4px; color: var(--c-text-primary); line-height: 1.4; }
.run-time { font-size: 12px; color: var(--c-text-secondary); }
.action-buttons { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.action-btn { padding: 7px 8px; border: none; border-radius: 8px; cursor: pointer; font-size: 12px; transition: all 0.2s; font-weight: 700; }
.action-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.report-btn { background: #16a34a; color: white; }
.report-btn:hover { filter: brightness(1.08); }
.export-btn { background: #1d4ed8; color: white; }
.export-btn:hover:not(:disabled) { filter: brightness(1.08); }
.export-btn:disabled { background: #d9d9d9; cursor: not-allowed; }
.delete-btn { background: #dc2626; color: white; }
.delete-btn:hover { filter: brightness(1.08); }

@media (max-width: 900px) {
  .runs-list { max-height: 260px; }
}
</style>
