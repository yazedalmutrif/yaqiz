import type { EventKind, SafetyEvent } from './types'

export const TZ = 'Asia/Riyadh'
// Gregorian calendar with Latin digits (ar-SA defaults to the Hijri calendar and Arabic-Indic digits).
const LOCALE = 'ar-SA-u-ca-gregory-nu-latn'

const timeFmt = new Intl.DateTimeFormat(LOCALE, { timeZone: TZ, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
const shortTimeFmt = new Intl.DateTimeFormat(LOCALE, { timeZone: TZ, hour: '2-digit', minute: '2-digit', hour12: false })
const dateFmt = new Intl.DateTimeFormat(LOCALE, { timeZone: TZ, year: 'numeric', month: 'long', day: 'numeric' })
const dateShortFmt = new Intl.DateTimeFormat(LOCALE, { timeZone: TZ, month: 'short', day: 'numeric' })
const rel = new Intl.RelativeTimeFormat('ar-u-nu-latn', { numeric: 'auto', style: 'short' })

export const fmtTime = (iso: string | Date) => timeFmt.format(new Date(iso))
export const fmtShortTime = (iso: string | Date) => shortTimeFmt.format(new Date(iso))
export const fmtDate = (iso: string | Date) => dateFmt.format(new Date(iso))
export const fmtDateShort = (iso: string | Date) => dateShortFmt.format(new Date(iso))
export const todayRiyadh = () => new Intl.DateTimeFormat('en-CA', { timeZone: TZ }).format(new Date())
export const dayToDate = (day: string) => new Date(`${day}T12:00:00+03:00`)

export function ago(iso: string, now = Date.now()): string {
  const s = Math.round((new Date(iso).getTime() - now) / 1000)
  if (Math.abs(s) < 60) return rel.format(s, 'second')
  if (Math.abs(s) < 3600) return rel.format(Math.round(s / 60), 'minute')
  if (Math.abs(s) < 86400) return rel.format(Math.round(s / 3600), 'hour')
  return rel.format(Math.round(s / 86400), 'day')
}

export function fmtDuration(sec: number): string {
  if (!sec || sec < 1) return 'أقل من ثانية'
  if (sec < 60) return `${Math.round(sec)} ث`
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  return s ? `${m} د ${s} ث` : `${m} د`
}

export const fmtNum = (n: number | null | undefined, digits = 0) =>
  n === null || n === undefined || Number.isNaN(n) ? '–' : n.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits })

/** A pixel/plan coordinate pair without thousands separators ("1100, 200", not "1,100, 200"). */
export const fmtCoord = (x: number, y: number) => `${Math.round(x)}, ${Math.round(y)}`

export const camCode = (id: number | null | undefined) => (id ? `CAM-${String(id).padStart(2, '0')}` : '–')

export const KIND_LABEL: Record<EventKind, string> = {
  zone_intrusion: 'دخول منطقة خطر',
  ppe_missing: 'نقص معدات الوقاية',
  man_down: 'سقوط عامل',
  sos: 'نداء استغاثة',
  midday_exposure: 'عمل وقت حظر الظهيرة',
  machine_proximity: 'اقتراب من معدة',
}
export const ITEM_LABEL: Record<string, string> = { helmet: 'بدون خوذة', vest: 'بدون سترة عاكسة', harness: 'بدون حزام أمان' }
export const SEVERITY_LABEL = { warning: 'تحذير', critical: 'حرج' } as const
export const LEVEL_LABEL = ['', 'منخفض', 'متوسط', 'مرتفع', 'حرج']
export const STATE_LABEL: Record<string, string> = {
  running: 'مباشر', waiting: 'بانتظار الصورة', loading: 'تحميل النماذج', connecting: 'جارٍ الاتصال',
  reconnecting: 'إعادة الاتصال', error: 'خطأ', stopped: 'متوقفة', starting: 'جارٍ التشغيل', live: 'مباشر',
  stalled: 'متوقفة عن التحليل',
}

/** An Arabic count with number agreement: 1 → one, 2 → dual, 3–10 → plural, 11–99 → singular (tamyiz). */
function countAr(n: number, w: { zero: string; one: string; two: string; plural: string; many: string; hundred: string }): string {
  if (n === 0) return w.zero
  if (n === 1) return w.one
  if (n === 2) return w.two
  const tail = n % 100
  const noun = tail >= 3 && tail <= 10 ? w.plural : tail >= 11 ? w.many : w.hundred
  return `${fmtNum(n)} ${noun}`
}

export const workersAr = (n: number) =>
  countAr(n, { zero: 'لا عمّال', one: 'عامل واحد', two: 'عاملان', plural: 'عمّال', many: 'عاملًا', hundred: 'عامل' })
export const eventsAr = (n: number) =>
  countAr(n, { zero: 'لا أحداث', one: 'حدث واحد', two: 'حدثان', plural: 'أحداث', many: 'حدثًا', hundred: 'حدث' })
export const minutesAr = (n: number) =>
  countAr(n, { zero: 'لا دقائق', one: 'دقيقة واحدة', two: 'دقيقتان', plural: 'دقائق', many: 'دقيقة', hundred: 'دقيقة' })

export function eventTitle(e: Pick<SafetyEvent, 'kind' | 'item'>): string {
  if (e.kind === 'ppe_missing' && e.item) return ITEM_LABEL[e.item] ?? KIND_LABEL.ppe_missing
  return KIND_LABEL[e.kind] ?? e.kind
}

export function phraseKey(kind: EventKind, item: string | null): string | null {
  if (kind === 'zone_intrusion') return 'zone'
  if (kind === 'ppe_missing') return item && ['helmet', 'vest', 'harness'].includes(item) ? item : null
  if (kind === 'man_down' || kind === 'sos') return 'emergency'
  if (kind === 'midday_exposure') return 'midday'
  if (kind === 'machine_proximity') return 'machine'
  return null
}

/** Scalloped "revision cloud" around a point (the drafting convention for "look here"). */
export function cloudPath(cx: number, cy: number, r: number, n = 11): string {
  const pts = Array.from({ length: n }, (_, i) => {
    const a = (i / n) * Math.PI * 2 - Math.PI / 2
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)]
  })
  let d = `M${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`
  for (let i = 1; i <= n; i++) {
    const [px, py] = pts[i - 1]
    const [x, y] = pts[i % n]
    const rr = (Math.hypot(x - px, y - py) * 0.62).toFixed(1)
    d += ` A${rr} ${rr} 0 0 1 ${x.toFixed(1)} ${y.toFixed(1)}`
  }
  return d
}

export function pointInPolygon(x: number, y: number, poly: [number, number][]): boolean {
  let inside = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i]
    const [xj, yj] = poly[j]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

export const centroid = (pts: [number, number][]): [number, number] => {
  const n = pts.length || 1
  return [pts.reduce((s, p) => s + p[0], 0) / n, pts.reduce((s, p) => s + p[1], 0) / n]
}
