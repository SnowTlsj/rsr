import { reactive, ref } from 'vue';

interface AromaParticle {
  id: number;
  x: number;
  y: number;
  drift: number;
  duration: number;
}

export function useMascotAroma(panelSelector = '.left-panel') {
  const mascotPos = reactive({ x: 18, y: 76 });
  const mascotSize = { w: 86, h: 122 };
  const dragState = reactive({
    active: false,
    pointerId: -1,
    offsetX: 0,
    offsetY: 0
  });
  const aromaParticles = ref<AromaParticle[]>([]);
  let particleId = 1;

  const getPanel = () => document.querySelector(panelSelector) as HTMLElement | null;

  const clampMascotPosition = (nextX: number, nextY: number) => {
    const panel = getPanel();
    if (!panel) {
      mascotPos.x = Math.max(0, nextX);
      mascotPos.y = Math.max(0, nextY);
      return;
    }
    const maxX = Math.max(0, panel.clientWidth - mascotSize.w - 8);
    const maxY = Math.max(0, panel.clientHeight - mascotSize.h - 8);
    mascotPos.x = Math.min(maxX, Math.max(8, nextX));
    mascotPos.y = Math.min(maxY, Math.max(56, nextY));
  };

  const onMascotPointerDown = (event: PointerEvent) => {
    const panel = getPanel();
    if (!panel) return;
    const panelRect = panel.getBoundingClientRect();
    dragState.active = true;
    dragState.pointerId = event.pointerId;
    dragState.offsetX = event.clientX - panelRect.left - mascotPos.x;
    dragState.offsetY = event.clientY - panelRect.top - mascotPos.y;
  };

  const onGlobalPointerMove = (event: PointerEvent) => {
    if (!dragState.active || event.pointerId !== dragState.pointerId) return;
    const panel = getPanel();
    if (!panel) return;
    const panelRect = panel.getBoundingClientRect();
    const nextX = event.clientX - panelRect.left - dragState.offsetX;
    const nextY = event.clientY - panelRect.top - dragState.offsetY;
    clampMascotPosition(nextX, nextY);
  };

  const onGlobalPointerUp = (event: PointerEvent) => {
    if (!dragState.active || event.pointerId !== dragState.pointerId) return;
    dragState.active = false;
    dragState.pointerId = -1;
  };

  const emitAroma = () => {
    const centerX = mascotPos.x + mascotSize.w / 2;
    const startY = mascotPos.y + 24;
    const batch = Array.from({ length: 9 }).map((_, index) => ({
      id: particleId++,
      x: centerX + (index - 3) * 6,
      y: startY + Math.random() * 10,
      drift: Math.round((Math.random() - 0.5) * 46),
      duration: 1300 + Math.round(Math.random() * 500)
    }));
    aromaParticles.value.push(...batch);
    window.setTimeout(() => {
      const ids = new Set(batch.map((item) => item.id));
      aromaParticles.value = aromaParticles.value.filter((item) => !ids.has(item.id));
    }, 2200);
  };

  const bind = () => {
    window.addEventListener('pointermove', onGlobalPointerMove);
    window.addEventListener('pointerup', onGlobalPointerUp);
  };

  const unbind = () => {
    window.removeEventListener('pointermove', onGlobalPointerMove);
    window.removeEventListener('pointerup', onGlobalPointerUp);
  };

  return {
    aromaParticles,
    mascotPos,
    onMascotPointerDown,
    emitAroma,
    bind,
    unbind
  };
}
