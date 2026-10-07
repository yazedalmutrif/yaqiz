import type {
  CalibPair, Camera, Health, Heat, Report, RiskGrid, RuntimeSettings, SafetyEvent, Site, VoiceManifest, Zone, ZoneInput,
} from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const isForm = body instanceof FormData
  const res = await fetch(path, {
    method,
    headers: body !== undefined && !isForm ? { 'Content-Type': 'application/json' } : undefined,
    body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
  })
  if (!res.ok) {
    let msg = `تعذّر الطلب (${res.status})`
    try {
      const j = await res.json()
      if (typeof j.detail === 'string') msg = j.detail
      else if (Array.isArray(j.detail)) msg = j.detail.map((d: { msg?: string }) => d.msg ?? '').filter(Boolean).join('، ')
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, msg)
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

type Query = Record<string, string | number | boolean | undefined | null>
const qs = (q: Query) =>
  new URLSearchParams(Object.entries(q).filter(([, v]) => v !== undefined && v !== null && v !== '').map(([k, v]) => [k, String(v)])).toString()

export const api = {
  health: () => request<Health>('GET', '/api/health'),
  site: () => request<Site>('GET', '/api/site'),
  updateSite: (b: Partial<Pick<Site, 'name' | 'lat' | 'lon'>>) => request<Site>('PUT', '/api/site', b),
  uploadPlan: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return request<Site>('POST', '/api/site/plan', fd)
  },
  zones: () => request<Zone[]>('GET', '/api/zones'),
  createZone: (z: ZoneInput) => request<Zone>('POST', '/api/zones', z),
  updateZone: (id: number, z: Partial<ZoneInput>) => request<Zone>('PUT', `/api/zones/${id}`, z),
  deleteZone: (id: number) => request<void>('DELETE', `/api/zones/${id}`),
  cameras: () => request<Camera[]>('GET', '/api/cameras'),
  createCamera: (b: { name: string; source: string; enabled?: boolean }) => request<Camera>('POST', '/api/cameras', b),
  updateCamera: (id: number, b: Partial<{ name: string; source: string; enabled: boolean }>) => request<Camera>('PUT', `/api/cameras/${id}`, b),
  deleteCamera: (id: number) => request<void>('DELETE', `/api/cameras/${id}`),
  startCamera: (id: number) => request<Camera>('POST', `/api/cameras/${id}/start`),
  stopCamera: (id: number) => request<Camera>('POST', `/api/cameras/${id}/stop`),
  calibrate: (id: number, pairs: CalibPair[]) =>
    request<{ camera: Camera; error_px: number; zones_in_view: Record<string, [number, number][]> }>('PUT', `/api/cameras/${id}/calibration`, { pairs }),
  clearCalibration: (id: number) => request<void>('DELETE', `/api/cameras/${id}/calibration`),
  events: (q: Query) => request<{ total: number; items: SafetyEvent[] }>('GET', `/api/events?${qs(q)}`),
  ack: (id: number) => request<SafetyEvent>('POST', `/api/events/${id}/ack`),
  risk: (date?: string, shift: 'day' | 'full' = 'day') => request<RiskGrid>('GET', `/api/risk?${qs({ date, shift })}`),
  report: (date?: string) => request<Report>('GET', `/api/report?${qs({ date })}`),
  heat: () => request<Heat>('GET', '/api/heat'),
  setHeat: (temperature_c: number, humidity: number) => request<Heat>('PUT', '/api/heat/manual', { temperature_c, humidity }),
  clearHeat: () => request<Heat>('DELETE', '/api/heat/manual'),
  settings: () => request<RuntimeSettings>('GET', '/api/settings'),
  saveSettings: (s: RuntimeSettings) => request<RuntimeSettings>('PUT', '/api/settings', s),
  voices: () => request<VoiceManifest>('GET', '/api/voices'),
}

export const streamUrl = (id: number) => `/api/cameras/${id}/stream.mjpg`
export const frameUrl = (id: number) => `/api/cameras/${id}/frame.jpg?t=${Date.now()}`
