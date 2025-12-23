<template>
  <MonitorView />
</template>

<script setup>
import MonitorView from './components/MonitorView.vue'
</script>

<style>
/* 这里去除浏览器默认的边距，保证全屏美观 */
body {
  margin: 0;
  padding: 0;
  background-color: #f0f2f5; /* 给背景一个浅灰色，突出主界面 */
}
</style>