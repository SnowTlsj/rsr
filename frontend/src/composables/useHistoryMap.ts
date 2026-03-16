import { onBeforeUnmount, ref } from 'vue';
import type { GpsPoint } from '@/types/history';

interface ToastApi {
  warning: (message: string, duration?: number) => void;
}

export function useHistoryMap(toast: ToastApi, defaultLongitude: number, defaultLatitude: number) {
  const gpsPoints = ref<GpsPoint[]>([]);
  const mapLoading = ref(false);

  let mapInstance: any = null;
  let overlay: any = null;

  const initMap = () => {
    const BMapGL = (window as any).BMapGL;
    if (!BMapGL) {
      toast.warning('地图加载失败，请检查网络连接', 5000);
      return;
    }

    mapInstance = new BMapGL.Map('history-map');
    const point = new BMapGL.Point(defaultLongitude, defaultLatitude);
    mapInstance.centerAndZoom(point, 14);
    mapInstance.enableScrollWheelZoom(true);
  };

  const renderPath = () => {
    if (!mapInstance) return;
    mapInstance.clearOverlays();
    overlay = null;

    const BMapGL = (window as any).BMapGL;
    const points = gpsPoints.value.map((point) => new BMapGL.Point(point.lon, point.lat));
    if (!points.length) return;

    if (points.length > 1) {
      const viewport = mapInstance.getViewport(points);
      mapInstance.centerAndZoom(viewport.center, viewport.zoom);
    } else {
      mapInstance.centerAndZoom(points[0], 17);
    }

    if (BMapGL.PointCollection) {
      overlay = new BMapGL.PointCollection(points, {
        size: 4,
        shape: (window as any).BMAP_POINT_SHAPE_CIRCLE,
        color: '#e53935'
      });
      mapInstance.addOverlay(overlay);
      return;
    }

    points.forEach((point: any) => {
      mapInstance.addOverlay(new BMapGL.Marker(point));
    });
  };

  const zoomIn = () => {
    if (mapInstance) {
      mapInstance.setZoom(mapInstance.getZoom() + 1);
    }
  };

  const zoomOut = () => {
    if (mapInstance) {
      mapInstance.setZoom(mapInstance.getZoom() - 1);
    }
  };

  const clearMap = () => {
    gpsPoints.value = [];
    if (mapInstance) {
      mapInstance.clearOverlays();
    }
  };

  const dispose = () => {
    if (mapInstance) {
      try {
        mapInstance.clearOverlays();
      } catch {
        // ignore map cleanup errors on unmount
      }
      mapInstance = null;
      overlay = null;
    }
  };

  onBeforeUnmount(dispose);

  return {
    gpsPoints,
    mapLoading,
    initMap,
    renderPath,
    zoomIn,
    zoomOut,
    clearMap,
    dispose
  };
}
