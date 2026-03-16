<template>
  <div v-if="visible" class="task-status-bar">
    <div class="status-item">
      <span class="status-label">任务名称:</span>
      <span class="status-value">{{ currentTaskName || '加载中...' }}</span>
    </div>
    <div class="status-item">
      <span class="status-label">任务ID:</span>
      <span class="status-value task-id">{{ runId ? runId.substring(0, 8) + '...' : '-' }}</span>
    </div>
    <div class="status-item">
      <span class="status-label">连接状态:</span>
      <span class="status-value" :class="connectionStatusClass">{{ connectionStatusText }}</span>
    </div>
    <div class="status-item">
      <span class="status-label">最后心跳:</span>
      <span class="status-value">{{ lastHeartbeatText }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean;
  currentTaskName: string;
  runId: string | null;
  connectionStatusText: string;
  connectionStatusClass: string;
  lastHeartbeatText: string;
}>();
</script>

<style scoped>
.task-status-bar {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  background: linear-gradient(90deg, #1e3a8a 0%, #1d4ed8 100%);
  border-bottom: 1px solid #1e3a8a;
  color: white;
  font-size: 14px;
  flex-wrap: wrap;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-label {
  font-weight: 500;
  opacity: 0.9;
}

.status-value {
  font-weight: 600;
  background: rgba(255, 255, 255, 0.16);
  padding: 4px 10px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
}

.status-value.task-id {
  font-size: 12px;
  letter-spacing: 0.5px;
}

.status-value.status-connected {
  background: rgba(76, 175, 80, 0.3);
  color: #c8e6c9;
}

.status-value.status-connecting {
  background: rgba(255, 193, 7, 0.3);
  color: #fff9c4;
}

.status-value.status-disconnected {
  background: rgba(244, 67, 54, 0.3);
  color: #ffcdd2;
}
</style>
