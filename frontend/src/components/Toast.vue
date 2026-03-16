<template>
  <Transition name="toast">
    <div v-if="visible && message" class="toast" :class="type">
      <div class="toast-content">
        <span class="toast-icon">{{ icon }}</span>
        <span class="toast-message">{{ message }}</span>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  visible: boolean;
  message: string;
  type?: 'success' | 'error' | 'warning' | 'info';
}>();

const icon = computed(() => {
  switch (props.type) {
    case 'success': return '✓';
    case 'error': return '✕';
    case 'warning': return '⚠';
    case 'info': return 'ℹ';
    default: return 'ℹ';
  }
});

</script>

<style scoped>
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
</style>
