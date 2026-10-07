import { useEffect, useState, type ComponentType, type SVGProps } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { ago, camCode, eventTitle, fmtNum, fmtTime } from '../lib/format'
import { useApi, useNow } from '../lib/hooks'
import { useLive } from '../lib/live'
import { voice } from '../lib/voice'
import {
  IconCalibrate, IconLog, IconMonitor, IconMute, IconPlan, IconReport, IconRisk, IconSettings, IconSpeaker, IconZones,
} from './Icons'

export interface RouteMeta { path: string; code: string; title: string; theme: 'feed' | 'paper'; Icon: ComponentType<SVGProps<SVGSVGElement>> }
export const ROUTES: RouteMeta[] = [
  { path: '/', code: 'S-01', title: 'المراقبة الحية', theme: 'feed', Icon: IconMonitor },
  { path: '/plan', code: 'S-02', title: 'مخطط الموقع', theme: 'paper', Icon: IconPlan },
  { path: '/zones', code: 'S-03', title: 'المناطق', theme: 'paper', Icon: IconZones },
  { path: '/calibration', code: 'S-04', title: 'معايرة الكاميرات', theme: 'paper', Icon: IconCalibrate },
  { path: '/log', code: 'S-05', title: 'السجل', theme: 'paper', Icon: IconLog },
  { path: '/risk', code: 'S-06', title: 'مؤشر الخطر', theme: 'paper', Icon: IconRisk },
  { path: '/report', code: 'S-07', title: 'التقرير اليومي', theme: 'paper', Icon: IconReport },
  { path: '/settings', code: 'S-08', title: 'الإعدادات', theme: 'paper', Icon: IconSettings },
]

const clockFmt = new Intl.DateTimeFormat('ar-SA-u-ca-gregory-nu-latn', { timeZone: 'Asia/Riyadh', weekday: 'long', hour: '2-digit', minute: '2-digit', hour12: false })

export function Shell() {
  const loc = useLocation()
  const navigate = useNavigate()
  const route = ROUTES.find((r) => r.path === loc.pathname) ?? ROUTES[0]
  const { state, upsert } = useLive()
  const now = useNow(1000)
  const site = useApi(api.site)
  const health = useApi(api.health)
  const [voiceOn, setVoiceOn] = useState(voice.enabled)

  useEffect(() => voice.subscribe(() => setVoiceOn(voice.enabled)), [])
  useEffect(() => {
    api.settings().then((s) => { voice.languages = s.voice_languages }).catch(() => undefined)
  }, [])
  useEffect(() => {
    const t = setInterval(() => void health.reload(), 15_000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => { document.title = `يقظ | ${route.title}` }, [route.title])

  const heat = state.heat
  const cams = Object.values(state.cameraStatus)
  const online = cams.filter((c) => c.state === 'running').length
  const critical = state.events.filter((e) => e.severity === 'critical' && !e.acknowledged && now - Date.parse(e.ts) < 30 * 60_000)
  const top = critical[0]

  const ackCritical = async () => {
    for (const e of critical) {
      try { upsert(await api.ack(e.id)) } catch { /* shown on next refresh */ }
    }
  }

  return (
    <div className="shell">
      <aside className="side" aria-label="القائمة الرئيسية">
        <div className="side__brand">
          <b>يقظ</b>
          <span>{site.data?.name ?? 'منظومة سلامة الموقع'}</span>
        </div>
        <nav className="side__nav">
          {ROUTES.map(({ path, code, title, Icon }) => (
            <NavLink key={path} to={path} end={path === '/'}>
              <Icon />
              <span>{title}</span>
              <span className="code">{code}</span>
            </NavLink>
          ))}
        </nav>
        <div className="side__status" aria-label="حالة النظام">
          <div><span>الاتصال المباشر</span><span>{state.connected ? 'متصل' : 'منقطع'}</span></div>
          <div><span>الكاميرات العاملة</span><span className="num">{online} / {cams.length || health.data?.cameras.length || 0}</span></div>
          <div><span>نموذج الوقاية</span><span className="ltr">{health.data?.ppe_model ?? '–'}</span></div>
          <div><span>المعالج الرسومي</span><span className="ltr" style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={health.data?.gpu ?? ''}>{health.data?.gpu?.replace('NVIDIA GeForce ', '') ?? 'CPU'}</span></div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar__title">
            <span className="code">{route.code}</span>
            <h1>{route.title}</h1>
          </div>
          <div className="topbar__tools">
            <span className="chip" title="توقيت الرياض">{clockFmt.format(now)}</span>
            {heat?.heat_index_c != null && (
              <span className={`chip chip--heat-${heat.category}`} title={`الحرارة ${heat.temperature_c}° والرطوبة ${heat.humidity}% (${heat.source === 'manual' ? 'إدخال يدوي' : 'Open-Meteo'})`}>
                مؤشر الحرارة <b className="num">{fmtNum(heat.heat_index_c, 0)}°</b> {heat.category_ar}
              </span>
            )}
            {heat?.midday_ban_active && <span className="chip chip--ban">حظر العمل تحت الشمس ساري</span>}
            <span className={`chip ${state.connected ? 'chip--live' : 'chip--down'}`}><span className="dot" />{state.connected ? 'مباشر' : 'منقطع'}</span>
            <button type="button" className={`btn ${voiceOn ? 'btn--hi' : ''}`} aria-pressed={voiceOn} onClick={() => voice.setEnabled(!voice.enabled)} title="تشغيل التنبيهات الصوتية على مكبر الموقع">
              {voiceOn ? <IconSpeaker /> : <IconMute />}
              {voiceOn ? 'مكبر الموقع مفعّل' : 'مكبر الموقع صامت'}
            </button>
          </div>
        </header>

        {top && (
          <div className="crit-banner" role="alert">
            <b>{eventTitle(top)}</b>
            <span>{top.detail.zone_name ?? 'خارج المناطق'}</span>
            <span className="ltr">{camCode(top.camera_id)}</span>
            <span title={fmtTime(top.ts)}>{ago(top.ts, now)}</span>
            {critical.length > 1 && <span>و{critical.length - 1} غيره</span>}
            <button type="button" className="btn btn--sm" onClick={() => navigate('/plan')}>عرض على المخطط</button>
            <button type="button" className="btn btn--sm" onClick={ackCritical}>تم الاطلاع</button>
          </div>
        )}

        <main className="page" data-theme={route.theme} id="main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
