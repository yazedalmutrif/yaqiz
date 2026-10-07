export type Severity = 'warning' | 'critical'
export type EventKind = 'zone_intrusion' | 'ppe_missing' | 'man_down' | 'sos' | 'midday_exposure' | 'machine_proximity'
export type Pt = [number, number]

export interface OperatorSignal { mode: 'simulated' | 'mqtt'; ok: boolean; topic?: string; error?: string }

export interface SafetyEvent {
  id: number
  ts: string
  ended_at: string | null
  kind: EventKind
  severity: Severity
  camera_id: number | null
  zone_id: number | null
  track_id: number | null
  item: 'helmet' | 'vest' | 'harness' | null
  detail: { zone_name?: string | null; operator_signal?: OperatorSignal; escalated?: boolean; closed_reason?: string; reason?: string; [k: string]: unknown }
  plan: Pt | null
  image: Pt | null
  snapshot_url: string | null
  acknowledged: boolean
  ack_at: string | null
  duration_s: number
}

export interface Zone {
  id: number
  name: string
  kind: 'no_entry' | 'ppe'
  points: Pt[]
  active: boolean
  outdoor: boolean
  require_helmet: boolean
  require_vest: boolean
  require_harness: boolean
  interlock: boolean
}
export type ZoneInput = Omit<Zone, 'id'>

export interface CameraStatus {
  id: number
  name?: string
  state: string
  error?: string | null
  fps?: number
  people?: number
  in_zone?: number
  latency_ms?: number | null
  latency_p95_ms?: number | null
  frame_size?: Pt | null
  calibrated?: boolean
  zones_in_view?: number[]
}

export interface CalibPair { plan: Pt; image: Pt }

export interface Camera {
  id: number
  name: string
  source: string
  enabled: boolean
  calibrated: boolean
  calib_error_px: number | null
  calib_pairs: CalibPair[]
  homography: number[][] | null
  frame_size: Pt | null
  status: CameraStatus
}

export interface Site {
  id: number
  name: string
  lat: number
  lon: number
  plan_url: string | null
  plan_width: number
  plan_height: number
  plan_version: number
  warning?: string
}

export interface Heat {
  temperature_c: number | null
  humidity: number | null
  heat_index_c: number | null
  category: number | null
  category_ar: string | null
  category_en: string | null
  midday_ban_active: boolean
  midday_ban: { from: string; to: string; start_hour: number; end_hour: number }
  source: 'open-meteo' | 'manual' | 'unavailable'
  fetched_at: string | null
  local_time: string
}

export interface Stats {
  camera_id: number
  fps: number
  latency_ms?: number | null
  latency_p95_ms?: number | null
  people: number
  in_zone: number
  state: string
  helmet_yes: number
  helmet_no: number
  vest_yes: number
  vest_no: number
}

export interface Track { id: number; x: number; y: number; status: 'ok' | 'warn' | 'critical' }

export interface RiskRow { zone_id: number | null; name: string; scores: number[]; levels: number[]; total: number }
export interface RiskGrid {
  date: string
  hours: number[]
  zones: RiskRow[]
  top: { zone_id: number | null; name: string; total: number } | null
  weights: Record<string, number>
  critical_bonus: number
}

export interface RuntimeSettings {
  voice_enabled: boolean
  voice_languages: string[]
  blur_stream: boolean
  site_require_helmet: boolean
  site_require_vest: boolean
  enter_frames: number
  exit_frames: number
  escalate_s: number
  ppe_hold_s: number
  man_down_s: number
  sos_hold_s: number
  cooldown_s: number
  lost_s: number
  det_conf: number
  pose_conf: number
  kp_conf: number
  min_person_px: number
  machine_gap: number
  midday_ban_from: string
  midday_ban_to: string
  midday_ban_start_hour: number
  midday_ban_end_hour: number
}

export interface Report {
  date: string
  generated_at: string
  totals: { events: number; critical: number; warning: number; acknowledged: number }
  by_kind: { kind: EventKind; label: string; count: number }[]
  by_zone: { zone_id: number | null; name: string; count: number }[]
  by_hour: number[]
  compliance: { helmet_pct: number | null; vest_pct: number | null; observations: number }
  coverage: { camera_id: number; name: string; minutes: number }[]
  critical_events: SafetyEvent[]
  risk: RiskGrid
  heat: Heat | null
}

export interface Health {
  status: string
  version: string
  time: string
  cameras: CameraStatus[]
  ppe_model: string | null
  capabilities: string[] | null
  gpu: string | null
  clients: number
}

export interface VoiceManifest {
  languages: { code: string; name: string }[]
  phrases: Record<string, Record<string, { text: string; url: string; available: boolean }>>
}
