export interface RunSummary {
  run_id: string;
  run_name: string;
  started_at: string;
  ended_at: string | null;
}

export interface GpsPoint {
  ts: string;
  lon: number;
  lat: number;
  alt_m?: number;
  heading_deg?: number;
}

export interface ReportTrendPoint {
  time: string;
  channel1: number;
  channel2: number;
  channel3: number;
  channel4: number;
  channel5: number;
}

export interface ReportData {
  run_id: string;
  run_name: string;
  started_at: string;
  ended_at: string;
  duration: string;
  total_seed_kg: string;
  total_distance_km: string;
  leak_distance_km: string;
  avg_speed_kmh: string;
  uniformity_index: string;
  channel1_kg: string;
  channel2_kg: string;
  channel3_kg: string;
  channel4_kg: string;
  channel5_kg: string;
  alarm_blocked_count: number;
  alarm_no_seed_count: number;
  gps_point_count: number;
  start_location: string;
  end_location: string;
  map_preview_url?: string;
  trend_data: ReportTrendPoint[];
}
