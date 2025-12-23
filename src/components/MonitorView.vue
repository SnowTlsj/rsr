<template>
  <div class="monitor-container">
    <header class="header">
      <div class="logo-section">
        <img src="@/assets/cau_logo.png" alt="CAU Logo" class="logo" />
      </div>
      <div class="title-section">
        <h1>肉苁蓉播种监测网页端</h1>
      </div>
    </header>

    <main class="main-content">
      <!-- 左侧数据面板 -->
      <div class="left-panel">
        <div class="data-grid">
          <!-- 使用 .toFixed(1) 格式化显示，保证显示一位小数 -->
          <div class="data-row"><label>通道1播种量：</label><div class="value-box">{{ sensorData.channel1.toFixed(1) }}</div><span class="unit">g</span></div>
          <div class="data-row"><label>通道2播种量：</label><div class="value-box">{{ sensorData.channel2.toFixed(1) }}</div><span class="unit">g</span></div>
          <div class="data-row"><label>通道3播种量：</label><div class="value-box">{{ sensorData.channel3.toFixed(1) }}</div><span class="unit">g</span></div>
          <div class="data-row"><label>通道4播种量：</label><div class="value-box">{{ sensorData.channel4.toFixed(1) }}</div><span class="unit">g</span></div>
          <div class="data-row"><label>通道5播种量：</label><div class="value-box">{{ sensorData.channel5.toFixed(1) }}</div><span class="unit">g</span></div>
          
          <!-- 总播种量 -->
          <div class="data-row"><label>总播种量：</label><div class="value-box">{{ totalSowing }}</div><span class="unit">g</span></div>
          
          <div class="data-row"><label>作业里程：</label><div class="value-box">{{ sensorData.mileage.toFixed(1) }}</div><span class="unit">m</span></div>
          <div class="data-row"><label>漏播里程：</label><div class="value-box">{{ sensorData.missedMileage.toFixed(1) }}</div><span class="unit">m</span></div>
          <div class="data-row single-row"><label>作业速度：</label><div class="value-box">{{ sensorData.speed.toFixed(1) }}</div><span class="unit">km/h</span></div>
        </div>

        <div class="indicators-area">
          <div class="indicator-item">
            <span>堵塞指示灯</span>
            <svg class="bulb-icon" :class="{ active: status.blocked }" viewBox="0 0 24 24"><path fill="currentColor" d="M9,21c0,0.55 0.45,1 1,1h4c0.55,0 1,-0.45 1,-1v-1H9V21z M12,2C8.13,2 5,5.13 5,9c0,2.38 1.19,4.47 3,5.74V17c0,0.55 0.45,1 1,1h6c0.55,0 1,-0.45 1,-1v-2.26c1.81,-1.27 3,-3.36 3,-5.74C19,5.13 15.87,2 12,2z"/></svg>
          </div>
          <div class="indicator-item">
            <span>缺种指示灯</span>
            <svg class="bulb-icon" :class="{ active: status.shortage }" viewBox="0 0 24 24"><path fill="currentColor" d="M9,21c0,0.55 0.45,1 1,1h4c0.55,0 1,-0.45 1,-1v-1H9V21z M12,2C8.13,2 5,5.13 5,9c0,2.38 1.19,4.47 3,5.74V17c0,0.55 0.45,1 1,1h6c0.55,0 1,-0.45 1,-1v-2.26c1.81,-1.27 3,-3.36 3,-5.74C19,5.13 15.87,2 12,2z"/></svg>
          </div>
        </div>
      </div>

      <!-- 右侧地图 -->
      <div class="right-panel">
        <h2 class="map-title">地图定位</h2>
        <div class="coords-info">
          <span>经度: {{ gpsData.longitude.toFixed(6) }} E</span>
          <span>纬度: {{ gpsData.latitude.toFixed(6) }} N</span>
        </div>
        <div class="map-border">
          <div id="baidu-map-container"></div>
          <button class="map-switch-btn" @click="toggleMapMode">{{ isSatelliteMode ? '切换二维地图' : '切换卫星实景' }}</button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { reactive, computed, onMounted, watch, ref } from 'vue';

const sensorData = reactive({
  channel1: 12.5,
  channel2: 13.2,
  channel3: 11.8,
  channel4: 12.0,
  channel5: 12.9,
  mileage: 150.5,
  missedMileage: 2.3,
  speed: 4.5
});

const totalSowing = computed(() => {
  const sum = Number(sensorData.channel1) + 
              Number(sensorData.channel2) + 
              Number(sensorData.channel3) + 
              Number(sensorData.channel4) + 
              Number(sensorData.channel5);
  return sum.toFixed(1);
});

const gpsData = reactive({
  longitude: 116.3650, 
  latitude: 40.0095
});

const status = reactive({ blocked: false, shortage: false });

let mapInstance = null;
let marker = null;
const isSatelliteMode = ref(true);

const initMap = () => {
  if (typeof BMapGL === 'undefined') {
    console.warn('百度地图加载失败。可能是广告插件拦截或AK错误。');
    return;
  }
  try {
    mapInstance = new BMapGL.Map('baidu-map-container');
    const point = new BMapGL.Point(gpsData.longitude, gpsData.latitude);
    mapInstance.centerAndZoom(point, 18);
    mapInstance.enableScrollWheelZoom(true);
    mapInstance.setMapType(BMAP_EARTH_MAP); 
    mapInstance.setTilt(45); 
    marker = new BMapGL.Marker(point);
    mapInstance.addOverlay(marker);
  } catch (e) {
    console.error("地图初始化出错:", e);
  }
};

const toggleMapMode = () => {
  if (!mapInstance) return;
  if (isSatelliteMode.value) {
    mapInstance.setMapType(BMAP_NORMAL_MAP);
    mapInstance.setTilt(0);
  } else {
    mapInstance.setMapType(BMAP_EARTH_MAP);
    mapInstance.setTilt(45);
  }
  isSatelliteMode.value = !isSatelliteMode.value;
};

watch(() => [gpsData.longitude, gpsData.latitude], ([newLng, newLat]) => {
  if (mapInstance && marker) {
    const newPoint = new BMapGL.Point(newLng, newLat);
    marker.setPosition(newPoint);
    mapInstance.panTo(newPoint);
  }
});

const fetchData = () => {
  // 预留接口位置
};

onMounted(() => {
  setTimeout(initMap, 500);
});
</script>

<style scoped>
/* --- 全局基础样式 (电脑端) --- */
.monitor-container { 
  font-family: "Microsoft YaHei", sans-serif; 
  max-width: 1400px; 
  margin: 0 auto; 
  background-color: #fff; 
}

.header { display: flex; align-items: center; padding: 10px 20px; border-bottom: 2px solid #ccc; }
.logo-section .logo { height: 60px; margin-right: 20px; }
.title-section h1 { font-size: 28px; margin: 0; letter-spacing: 2px; }

/* 主体区域 */
.main-content { 
  display: flex; 
  flex-direction: row; 
  border: 2px dashed #333; 
  margin: 20px; 
  min-height: 650px; 
}

/* 左侧面板 */
.left-panel { 
  flex: 3; 
  padding: 30px; 
  display: flex; 
  flex-direction: column; 
  justify-content: space-between; 
}

/* 右侧面板 */
.right-panel { 
  flex: 2; 
  border-left: 2px solid #000; 
  padding: 20px; 
  display: flex; 
  flex-direction: column; 
}

/* 数据网格 */
.data-grid { display: flex; flex-wrap: wrap; gap: 20px; }
.data-row { display: flex; align-items: center; width: 48%; margin-bottom: 25px; }
.single-row { width: 100%; }

/* 电脑端 Label 样式 */
.data-row label { font-size: 20px; width: 160px; text-align: right; margin-right: 10px; }

.value-box { background-color: #5b9bd5; border: 1px solid #333; border-radius: 8px; height: 45px; flex-grow: 1; display: flex; align-items: center; justify-content: center; color: white; font-size: 22px; font-weight: bold; box-shadow: 2px 2px 5px rgba(0,0,0,0.2); }
.unit { font-size: 20px; margin-left: 10px; width: 40px; font-style: italic; font-family: "Times New Roman", serif; }

.indicators-area { display: flex; justify-content: space-around; margin-top: 40px; padding: 0 50px; }
.indicator-item { display: flex; flex-direction: column; align-items: center; }
.indicator-item span { font-size: 22px; margin-bottom: 15px; }
.bulb-icon { width: 80px; height: 80px; fill: white; stroke: black; stroke-width: 2px; transition: fill 0.3s ease; }
.bulb-icon.active { fill: #ff0000; stroke: #b30000; filter: drop-shadow(0 0 10px rgba(255, 0, 0, 0.8)); }

.map-title { text-align: center; font-size: 26px; margin-bottom: 10px; margin-top: 0; }
.coords-info { display: flex; justify-content: space-around; font-size: 20px; margin-bottom: 15px; }
.map-border { flex-grow: 1; border: 2px solid #999; position: relative; min-height: 300px; }
#baidu-map-container { width: 100%; height: 100%; background-color: #f0f0f0; }
.map-switch-btn { position: absolute; top: 10px; right: 10px; z-index: 999; padding: 8px 15px; background-color: rgba(255, 255, 255, 0.9); border: 1px solid #999; border-radius: 4px; font-size: 14px; cursor: pointer; box-shadow: 0 2px 5px rgba(0,0,0,0.3); font-weight: bold; transition: background 0.3s; }
.map-switch-btn:hover { background-color: #e6e6e6; }

/* ============================================= */
/* 📱 移动端深度适配 (二等分卡片布局)             */
/* ============================================= */
@media (max-width: 900px) {
  /* 1. 头部调整 */
  .header { flex-direction: column; text-align: center; }
  .logo-section .logo { margin-right: 0; margin-bottom: 5px; height: 40px; }
  .title-section h1 { font-size: 18px; margin-bottom: 5px; }

  /* 2. 主体改为上下结构 */
  .main-content {
    flex-direction: column;
    margin: 5px;
    border: 1px dashed #ccc;
  }

  .left-panel {
    padding: 10px;
    border-bottom: 1px solid #eee;
  }

  /* 3. 数据网格：关键布局 */
  .data-grid {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between; /* 两端对齐，中间留空 */
    gap: 8px; /* 行间距和列间距 */
  }

  /* 4. 单个数据卡片 (二等分) */
  .data-row {
    width: 48%; /* 强制宽度接近一半，实现一行两个 */
    margin-bottom: 0; /* 由 gap 控制间距 */
    
    /* 【关键技巧】让内容换行：标签在上，数字在下 */
    flex-wrap: wrap; 
    justify-content: center;
    
    /* 给个小边框让它像个卡片，看起来更整齐 */
    border: 1px solid #eee; 
    border-radius: 6px;
    padding: 8px 4px;
    background-color: rgba(240, 240, 240, 0.5); /* 浅灰色背景区分 */
  }

  /* 特殊处理：速度栏还是独占一行比较好看，或者你也想让它变一半就把这行删了 */
  .single-row { width: 100%; }

  /* 5. 标签文字：强制独占一行，居中 */
  .data-row label {
    width: 100%; /* 占满宽度，迫使数字框换行到下一行 */
    text-align: center;
    margin-right: 0;
    font-size: 13px;
    margin-bottom: 5px; /* 标签和数字框的间距 */
    color: #333;
  }

  /* 6. 数字框 */
  .value-box {
    height: 35px;
    font-size: 18px;
    /* 宽度自动填满剩余空间 */
    min-width: 60px; 
  }

  /* 7. 单位 */
  .unit {
    font-size: 12px;
    margin-left: 4px;
    width: auto;
  }

  /* 指示灯 */
  .indicators-area { margin-top: 15px; padding: 0; }
  .bulb-icon { width: 45px; height: 45px; }
  .indicator-item span { font-size: 14px; }

  /* 地图区域 */
  .right-panel {
    border-left: none;
    padding: 10px;
    height: 400px;
  }
  .map-title { font-size: 18px; }
  .coords-info { font-size: 12px; }
}
</style>