import { onBeforeUnmount, ref, watch } from 'vue';

interface ToastApi {
  error: (message: string, duration?: number) => void;
  warning: (message: string, duration?: number) => void;
}

interface GpsState {
  longitude: number;
  latitude: number;
}

export function useMonitorMap(gpsData: GpsState, toast: ToastApi) {
  const isSatelliteMode = ref(true);
  const gpsTrail = ref<Array<{ lon: number; lat: number }>>([]);

  let mapInstance: any = null;
  let marker: any = null;
  let polyline: any = null;
  let trailRenderTimer: number | null = null;

  const initMap = () => {
    const BMapGL = (window as any).BMapGL;
    if (!BMapGL) {
      toast.warning('地图加载失败，请检查网络连接', 5000);
      return;
    }
    try {
      mapInstance = new BMapGL.Map('baidu-map-container');
      const point = new BMapGL.Point(gpsData.longitude, gpsData.latitude);
      mapInstance.centerAndZoom(point, 18);
      mapInstance.enableScrollWheelZoom(true);
      mapInstance.setMapType((window as any).BMAP_EARTH_MAP);
      mapInstance.setTilt(45);
      marker = new BMapGL.Marker(point);
      mapInstance.addOverlay(marker);
    } catch (e) {
      console.error('Map init failed', e);
      toast.error('地图初始化失败');
    }
  };

  const renderTrail = () => {
    if (!mapInstance) return;
    const BMapGL = (window as any).BMapGL;
    const points = gpsTrail.value.map((point) => new BMapGL.Point(point.lon, point.lat));
    if (points.length < 2) return;
    if (!polyline) {
      polyline = new BMapGL.Polyline(points, {
        strokeColor: '#ff0000',
        strokeWeight: 3,
        strokeOpacity: 0.8
      });
      mapInstance.addOverlay(polyline);
      return;
    }
    polyline.setPath(points);
  };

  const toggleMapMode = () => {
    if (!mapInstance) return;
    if (isSatelliteMode.value) {
      mapInstance.setMapType((window as any).BMAP_NORMAL_MAP);
      mapInstance.setTilt(0);
    } else {
      mapInstance.setMapType((window as any).BMAP_EARTH_MAP);
      mapInstance.setTilt(45);
    }
    isSatelliteMode.value = !isSatelliteMode.value;
  };

  const resetTrail = () => {
    gpsTrail.value = [];
    if (polyline && mapInstance) {
      mapInstance.removeOverlay(polyline);
      polyline = null;
    }
  };

  watch(
    () => [gpsData.longitude, gpsData.latitude],
    ([newLng, newLat]) => {
      if (!mapInstance || !marker) return;
      const BMapGL = (window as any).BMapGL;
      const newPoint = new BMapGL.Point(newLng, newLat);
      marker.setPosition(newPoint);
      mapInstance.panTo(newPoint);
      gpsTrail.value.push({ lon: newLng, lat: newLat });
      if (trailRenderTimer) {
        window.clearTimeout(trailRenderTimer);
      }
      trailRenderTimer = window.setTimeout(renderTrail, 250);
    }
  );

  const dispose = () => {
    if (trailRenderTimer) {
      window.clearTimeout(trailRenderTimer);
      trailRenderTimer = null;
    }
    if (mapInstance) {
      try {
        mapInstance.clearOverlays();
      } catch {
        // ignore map cleanup errors on unmount
      }
      mapInstance = null;
      marker = null;
      polyline = null;
    }
  };

  onBeforeUnmount(dispose);

  return {
    isSatelliteMode,
    initMap,
    toggleMapMode,
    resetTrail,
    dispose
  };
}
