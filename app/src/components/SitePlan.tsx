import { useRef, type ReactNode } from 'react'
import { centroid } from '../lib/format'
import type { Pt, Site, Zone } from '../lib/types'

interface Props {
  site: Site
  zones: Zone[]
  selectedZoneId?: number | null
  zoneCounts?: Record<number, number>
  picking?: boolean
  onPick?: (pt: Pt) => void
  onZoneClick?: (z: Zone) => void
  children?: ReactNode            // extra SVG drawn in plan coordinates (on top of the zones)
  label?: string
}

/** The site plan with zones as an SVG overlay in plan-pixel coordinates (the same space the API uses). */
export function SitePlan({ site, zones, selectedZoneId, zoneCounts, picking, onPick, onZoneClick, children, label }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const w = site.plan_width
  const h = site.plan_height
  const fs = w / 72

  const toPlan = (clientX: number, clientY: number): Pt => {
    const r = svgRef.current!.getBoundingClientRect()
    return [Math.round(((clientX - r.left) / r.width) * w * 10) / 10, Math.round(((clientY - r.top) / r.height) * h * 10) / 10]
  }

  return (
    <div className={`plan ${picking ? 'is-picking' : ''}`} style={{ aspectRatio: `${w} / ${h}` }}>
      {site.plan_url ? (
        <img src={`${site.plan_url}?v=${site.plan_version}`} alt="" draggable={false} />
      ) : (
        <div className="empty">لم يُرفع مخطط للموقع بعد. ارفعه من صفحة «المناطق».</div>
      )}
      <svg
        ref={svgRef}
        viewBox={`0 0 ${w} ${h}`}
        role="img"
        aria-label={label ?? `مخطط الموقع وعليه ${zones.length} مناطق`}
        onClick={picking && onPick ? (e) => onPick(toPlan(e.clientX, e.clientY)) : undefined}
      >
        <defs>
          <pattern id="hatch-red" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="14" height="14" fill="rgba(220,46,38,0.10)" />
            <line x1="0" y1="0" x2="0" y2="14" stroke="rgba(220,46,38,0.55)" strokeWidth="3" />
          </pattern>
          <radialGradient id="heat-grad">
            <stop offset="0%" stopColor="#dc2e26" stopOpacity="0.55" />
            <stop offset="60%" stopColor="#ff5b1f" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#ff5b1f" stopOpacity="0" />
          </radialGradient>
        </defs>
        {zones.map((z) => {
          const [cx, cy] = centroid(z.points)
          const cls = `zone-shape zone-shape--${z.kind} ${z.kind === 'no_entry' && !z.active ? 'is-off' : ''} ${selectedZoneId === z.id ? 'is-selected' : ''}`
          const count = zoneCounts?.[z.id] ?? 0
          return (
            <g key={z.id} onClick={onZoneClick && !picking ? (e) => { e.stopPropagation(); onZoneClick(z) } : undefined} style={{ cursor: onZoneClick && !picking ? 'pointer' : undefined }}>
              <polygon className={cls} points={z.points.map((p) => p.join(',')).join(' ')} />
              <text className="zone-label" x={cx} y={cy} fontSize={fs} textAnchor="middle" dominantBaseline="central">{z.name}</text>
              {count > 0 && (
                <g transform={`translate(${cx} ${cy + fs * 1.6})`}>
                  <circle r={fs * 0.95} fill={z.kind === 'no_entry' && z.active ? '#dc2e26' : '#22262a'} />
                  <text className="zone-count" fontSize={fs * 1.05} textAnchor="middle" dominantBaseline="central">{count}</text>
                </g>
              )}
            </g>
          )
        })}
        {children}
      </svg>
    </div>
  )
}
