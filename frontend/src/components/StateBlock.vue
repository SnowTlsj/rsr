<template>
  <div class="state-block" :class="variant">
    <div class="state-title">{{ title }}</div>
    <div v-if="description" class="state-description">{{ description }}</div>
    <button v-if="actionLabel" class="state-action" type="button" @click="emit('action')">{{ actionLabel }}</button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string;
  description?: string;
  actionLabel?: string;
  variant?: 'empty' | 'loading' | 'error';
}>();

const emit = defineEmits<{
  action: [];
}>();
</script>

<style scoped>
.state-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border-radius: 10px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: var(--shadow-sm);
}

.state-block.empty {
  color: var(--c-text-secondary);
}

.state-block.loading {
  color: #1f2937;
}

.state-block.error {
  border-color: #fecaca;
  background: #fff7f7;
  color: #991b1b;
}

.state-title {
  font-size: 13px;
  font-weight: 700;
}

.state-description {
  font-size: 12px;
  line-height: 1.5;
}

.state-action {
  align-self: flex-start;
  padding: 7px 12px;
  border: 1px solid #a8bfd8;
  border-radius: 8px;
  background: #eef4ff;
  color: #1e3a8a;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
</style>
