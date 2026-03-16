<template>
  <div class="left-panel">
    <h2 class="section-title">播种信息</h2>
    <div
      class="cistanche-mascot"
      :style="{ left: `${mascotX}px`, top: `${mascotY}px` }"
      role="button"
      tabindex="0"
      @pointerdown="emit('mascot-pointer-down', $event)"
      @click.stop="emit('mascot-activate')"
      @keydown.enter.prevent="emit('mascot-activate')"
      @keydown.space.prevent="emit('mascot-activate')"
    >
      <div class="mascot-stem"></div>
      <div class="mascot-cap"></div>
      <div class="mascot-eye left"></div>
      <div class="mascot-eye right"></div>
      <div class="mascot-smile"></div>
    </div>
    <div class="aroma-layer" aria-hidden="true">
      <span
        v-for="particle in aromaParticles"
        :key="particle.id"
        class="aroma-particle"
        :style="{ left: `${particle.x}px`, top: `${particle.y}px`, '--drift': `${particle.drift}px`, '--duration': `${particle.duration}ms` }"
      />
    </div>
    <div class="data-grid">
      <div class="data-row"><label>通道1播种量：</label><div class="value-box">{{ sensorData.channel1.toFixed(1) }}</div><span class="unit">g</span><span class="alarm-light" :class="{ active: alarmData.channel1 }"></span></div>
      <div class="data-row"><label>通道2播种量：</label><div class="value-box">{{ sensorData.channel2.toFixed(1) }}</div><span class="unit">g</span><span class="alarm-light" :class="{ active: alarmData.channel2 }"></span></div>
      <div class="data-row"><label>通道3播种量：</label><div class="value-box">{{ sensorData.channel3.toFixed(1) }}</div><span class="unit">g</span><span class="alarm-light" :class="{ active: alarmData.channel3 }"></span></div>
      <div class="data-row"><label>通道4播种量：</label><div class="value-box">{{ sensorData.channel4.toFixed(1) }}</div><span class="unit">g</span><span class="alarm-light" :class="{ active: alarmData.channel4 }"></span></div>
      <div class="data-row"><label>通道5播种量：</label><div class="value-box">{{ sensorData.channel5.toFixed(1) }}</div><span class="unit">g</span><span class="alarm-light" :class="{ active: alarmData.channel5 }"></span></div>
      <div class="data-row"><label>总播种量：</label><div class="value-box">{{ totalSowing }}</div><span class="unit">g</span></div>
      <div class="data-row"><label>作业里程：</label><div class="value-box">{{ sensorData.mileage.toFixed(1) }}</div><span class="unit">m</span></div>
      <div class="data-row"><label>漏播里程：</label><div class="value-box">{{ sensorData.missedMileage.toFixed(1) }}</div><span class="unit">m</span></div>
      <div class="data-row"><label>作业速度：</label><div class="value-box">{{ sensorData.speed.toFixed(1) }}</div><span class="unit">km/h</span></div>
      <div class="data-row"><label>匀播指数：</label><div class="value-box">{{ uniformityIndex }}</div><span class="unit">g/m</span></div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  sensorData: {
    channel1: number;
    channel2: number;
    channel3: number;
    channel4: number;
    channel5: number;
    mileage: number;
    missedMileage: number;
    speed: number;
  };
  alarmData: {
    channel1: number;
    channel2: number;
    channel3: number;
    channel4: number;
    channel5: number;
  };
  totalSowing: string;
  uniformityIndex: string;
  mascotX: number;
  mascotY: number;
  aromaParticles: Array<{ id: number; x: number; y: number; drift: number; duration: number }>;
}>();

const emit = defineEmits<{
  'mascot-pointer-down': [event: PointerEvent];
  'mascot-activate': [];
}>();
</script>

<style scoped>
.left-panel { position: relative; padding: 16px 14px 12px; display: flex; flex-direction: column; min-height: 0; }
.section-title { text-align: left; font-size: 24px; font-weight: 800; color: var(--c-text-primary); margin: 0 0 12px 0; }
.cistanche-mascot {
  position: absolute;
  left: 20px;
  bottom: 20px;
  width: 86px;
  height: 122px;
  cursor: grab;
  opacity: 0.82;
  z-index: 3;
  touch-action: none;
  user-select: none;
}
.cistanche-mascot:active { cursor: grabbing; }
.mascot-stem {
  position: absolute;
  left: 16px;
  bottom: 0;
  width: 56px;
  height: 96px;
  border-radius: 28px 28px 18px 18px;
  background: linear-gradient(180deg, #d18d56 0%, #af6d3f 68%, #93552f 100%);
  box-shadow: inset 0 -6px 0 rgba(0, 0, 0, 0.08), inset 8px 0 0 rgba(255, 255, 255, 0.15);
}
.mascot-cap {
  position: absolute;
  left: 8px;
  bottom: 78px;
  width: 72px;
  height: 34px;
  border-radius: 32px;
  background: linear-gradient(180deg, #e3a56a 0%, #ba7a49 100%);
  box-shadow: inset 0 -4px 0 rgba(0, 0, 0, 0.08);
}
.mascot-eye {
  position: absolute;
  bottom: 42px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3d2a1d;
}
.mascot-eye.left { left: 34px; }
.mascot-eye.right { left: 48px; }
.mascot-smile {
  position: absolute;
  left: 36px;
  bottom: 30px;
  width: 12px;
  height: 8px;
  border-bottom: 2px solid #5a3b26;
  border-radius: 0 0 10px 10px;
}
.aroma-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 2;
}
.aroma-particle {
  position: absolute;
  width: 12px;
  height: 18px;
  background: linear-gradient(160deg, rgba(255, 237, 181, 0.95) 0%, rgba(236, 191, 113, 0.9) 45%, rgba(196, 142, 73, 0.82) 100%);
  border-radius: 82% 22% 70% 30% / 70% 36% 64% 30%;
  transform-origin: 50% 100%;
  box-shadow: inset -1px -1px 0 rgba(123, 84, 43, 0.22), 0 1px 2px rgba(121, 88, 52, 0.24);
  animation: aroma-rise var(--duration) ease-out forwards;
}
@keyframes aroma-rise {
  0% { transform: translate(0, 0) rotate(-8deg) scale(0.72); opacity: 0.95; }
  35% { opacity: 0.8; }
  100% { transform: translate(var(--drift), -76px) rotate(26deg) scale(1.1); opacity: 0; }
}
.data-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); grid-template-rows: repeat(5, minmax(0, 1fr)); gap: 14px; flex: 1; min-height: 0; }
.data-row { display: grid; grid-template-columns: 138px 1fr auto auto; align-items: center; width: 100%; margin-bottom: 0; padding: 10px 12px; border: 1px solid rgba(226, 232, 240, 0.85); border-radius: 10px; background: rgba(255, 255, 255, 0.82); height: 100%; min-height: 78px; }
.data-row label { font-size: 15px; width: auto; text-align: left; margin-right: 0; color: #334155; font-weight: 700; }
.value-box { background: linear-gradient(180deg, #2563eb 0%, #1d4ed8 100%); border: 1px solid #1e40af; border-radius: 9px; height: 40px; display: flex; align-items: center; justify-content: center; color: white; font-size: 23px; font-weight: 800; letter-spacing: 0.2px; box-shadow: inset 0 -2px 0 rgba(0,0,0,0.15); }
.unit { font-size: 13px; margin-left: 8px; width: 38px; font-style: normal; font-family: var(--font-main); color: #475569; font-weight: 700; text-align: center; }
.alarm-light { width: 16px; height: 16px; border-radius: 50%; background-color: var(--c-success); margin-left: 8px; box-shadow: 0 0 0 3px rgba(46,125,50,0.12); transition: background-color 0.3s; }
.alarm-light.active { background-color: var(--c-danger); box-shadow: 0 0 10px var(--c-danger); }

@media (max-width: 900px) {
  .left-panel { padding: 10px; border-bottom: 1px solid #e7edf4; }
  .section-title { font-size: 22px; }
  .data-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); grid-template-rows: repeat(5, minmax(0, 1fr)); gap: 10px; }
  .data-row { grid-template-columns: 1fr; grid-template-areas: 'label' 'value'; gap: 6px; padding: 8px; min-height: 92px; position: relative; }
  .data-row label { grid-area: label; font-size: 13px; text-align: center; }
  .value-box { grid-area: value; height: 34px; font-size: 17px; }
  .unit { position: absolute; right: 8px; bottom: 8px; font-size: 11px; }
  .alarm-light { position: absolute; right: 8px; top: 8px; width: 12px; height: 12px; margin-left: 0; }
  .cistanche-mascot { display: none; }
  .aroma-layer { display: none; }
}
</style>
