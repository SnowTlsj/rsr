/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE: string
  readonly VITE_WS_BASE: string
  readonly VITE_MACHINE_ID: string
  readonly VITE_BAIDU_AK: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare const BMapGL: any
declare const BMAP_EARTH_MAP: any
declare const BMAP_NORMAL_MAP: any
declare const BMAP_POINT_SHAPE_CIRCLE: any

interface Window {
  BMapGL: any
}
