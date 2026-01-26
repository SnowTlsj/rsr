import { createRouter, createWebHistory } from 'vue-router';
import MonitorView from '@/components/MonitorView.vue';
import HistoryView from '@/views/HistoryView.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'monitor', component: MonitorView },
    { path: '/history', name: 'history', component: HistoryView }
  ]
});

export default router;
