// Yaqiz landing page: motion layer.
// GSAP ScrollTrigger for scroll-linked/pinned sequences, Lenis for smooth scrolling.
// Every animation has a static end state for prefers-reduced-motion, and loops pause
// when off-screen or when the tab is hidden. Arabic text is never split below word level
// (splitting letters breaks Arabic joining).

import '@fontsource/changa/500.css'
import '@fontsource/changa/700.css'
import '@fontsource/changa/800.css'
import '@fontsource/ibm-plex-sans-arabic/400.css'
import '@fontsource/ibm-plex-sans-arabic/500.css'
import '@fontsource/ibm-plex-sans-arabic/600.css'
import '@fontsource/ibm-plex-sans-arabic/700.css'
import './styles.css'

import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { DrawSVGPlugin } from 'gsap/DrawSVGPlugin'
import { MotionPathPlugin } from 'gsap/MotionPathPlugin'
import Lenis from 'lenis'

gsap.registerPlugin(ScrollTrigger, DrawSVGPlugin, MotionPathPlugin)

const $ = (s, r = document) => r.querySelector(s)
const $$ = (s, r = document) => [...r.querySelectorAll(s)]
const REDUCE = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const lerp = (a, b, t) => a + (b - a) * t
const pad = (n) => String(n).padStart(2, '0')

/* ------------------------------------------------------------------ smooth scroll */
let lenis = null
if (!REDUCE) {
  lenis = new Lenis({ lerp: 0.1 })
  lenis.on('scroll', ScrollTrigger.update)
  gsap.ticker.add((time) => lenis.raf(time * 1000))
  gsap.ticker.lagSmoothing(0)
}

$$('a[href^="#"]').forEach((a) => {
  a.addEventListener('click', (e) => {
    const id = a.getAttribute('href')
    const target = id && id.length > 1 ? document.querySelector(id) : null
    if (!target) return
    e.preventDefault()
    if (lenis) lenis.scrollTo(target, { offset: 0 })
    else target.scrollIntoView()
    history.replaceState(null, '', id)
  })
})

/* Loops play only while their section is on screen and the tab is visible. */
function loopWhenVisible(anim, trigger) {
  let inView = false
  const sync = () => (inView && !document.hidden ? anim.play() : anim.pause())
  ScrollTrigger.create({ trigger, start: 'top bottom', end: 'bottom top', onToggle: (s) => { inView = s.isActive; sync() } })
  document.addEventListener('visibilitychange', sync)
}

/* ------------------------------------------------------------------ top bar */
gsap.to('.dimline__fill', { scaleX: 1, ease: 'none', scrollTrigger: { start: 0, end: 'max', scrub: true } })

/* ------------------------------------------------------------------ S-00 hero: live site plan */
// Revision cloud: scalloped arcs around a point (the drawing convention for "look here").
function cloudPath(cx, cy, r, n = 11) {
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

;(function hero() {
  const w3 = $('#w3')
  const cloud = $('#hero-cloud')
  const tag = $('#hero-alert')
  const VIOLATION = { x: 520, y: 520 }
  cloud.setAttribute('d', cloudPath(VIOLATION.x, VIOLATION.y, 40))

  gsap.set('#w1', { x: 200, y: 300 })
  gsap.set('#w2', { x: 150, y: 470 })
  gsap.set('#w4', { x: 600, y: 205 })

  if (REDUCE) { // static frame: the moment the alert fires
    gsap.set(w3, { x: VIOLATION.x, y: VIOLATION.y })
    w3.classList.add('is-alert')
    gsap.set(cloud, { drawSVG: '100%' })
    gsap.set(tag, { autoAlpha: 1 })
    return
  }

  gsap.set(w3, { x: 250, y: 560 })
  gsap.set(cloud, { drawSVG: '0%' })
  gsap.set(tag, { autoAlpha: 0, y: 8 })

  const loops = gsap.timeline({ paused: true })
  loops.to('#jib', { rotation: 360, svgOrigin: '640 250', duration: 26, ease: 'none', repeat: -1 }, 0)
  loops.to('#w1', { keyframes: [{ x: 330, y: 320, duration: 3 }, { x: 330, y: 200, duration: 2.4 }, { x: 200, y: 300, duration: 3 }], ease: 'none', repeat: -1 }, 0)
  loops.to('#w2', { x: 380, duration: 5, ease: 'sine.inOut', yoyo: true, repeat: -1 }, 0)
  loops.to('#w4', { x: 565, y: 300, duration: 4, ease: 'sine.inOut', yoyo: true, repeat: -1 }, 0)

  const alertTl = gsap.timeline({ paused: true, repeat: -1, repeatDelay: 0.8 })
  alertTl
    .set(w3, { x: 250, y: 560 })
    .to(w3, { x: VIOLATION.x, y: VIOLATION.y, duration: 3.2, ease: 'none' })
    .call(() => w3.classList.add('is-alert'))
    .to(cloud, { drawSVG: '100%', duration: 0.7, ease: 'power2.out' })
    .to(tag, { autoAlpha: 1, y: 0, duration: 0.35 }, '<0.15')
    .to('#cone-2', { opacity: 0.5, duration: 0.25, yoyo: true, repeat: 3 }, '<')
    .to({}, { duration: 2.6 })
    .to(tag, { autoAlpha: 0, y: 8, duration: 0.3 })
    .to(cloud, { drawSVG: '0%', duration: 0.4 }, '<')
    .call(() => w3.classList.remove('is-alert'))
    .to(w3, { x: 250, y: 560, duration: 2.6, ease: 'none' })

  const both = { play: () => { loops.play(); alertTl.play() }, pause: () => { loops.pause(); alertTl.pause() } }
  loopWhenVisible(both, '.hero')
})()

/* ------------------------------------------------------------------ S-01 statement + counters */
;(function statement() {
  const el = $('#statement')
  const text = el.textContent.trim()
  el.textContent = ''
  text.split(/\s+/).forEach((word, i, arr) => {
    const span = document.createElement('span')
    span.className = 'w'
    span.textContent = word
    el.appendChild(span)
    if (i < arr.length - 1) el.appendChild(document.createTextNode(' '))
  })
  if (REDUCE) return
  gsap.fromTo('#statement .w', { opacity: 0.12 }, {
    opacity: 1, stagger: 0.1, ease: 'none',
    scrollTrigger: { trigger: el, start: 'top 85%', end: 'top 40%', scrub: true },
  })
})()

$$('.count').forEach((el) => {
  const to = parseFloat(el.dataset.to)
  const fmt = (v) => (el.dataset.format === 'dec2' ? v.toFixed(2) : Math.round(v).toLocaleString('en-US'))
  if (REDUCE) { el.textContent = fmt(to); return }
  const state = { v: 0 }
  el.textContent = fmt(0)
  ScrollTrigger.create({
    trigger: el, start: 'top 88%', once: true,
    onEnter: () => gsap.to(state, { v: to, duration: 1.6, ease: 'power2.out', onUpdate: () => { el.textContent = fmt(state.v) } }),
  })
})

/* ------------------------------------------------------------------ S-02 plan → camera (pinned) */
;(function planToCamera() {
  const sec = $('#plan-to-camera')
  const zone = $('.p2c-zone')
  const photo = $('.p2c-photo')
  const plan = $('.p2c-plan')
  const label = $('.p2c-zone-label')
  const feet = $$('.p2c-feet > g')
  const alert = $('.p2c-alert')
  const voices = $$('.voices li')
  const steps = $$('.step')
  const stateEl = $('.feed-bar__state')
  // Plan strip along the east slab edge → the same zone as the prototype draws it on the camera
  // frame (configs/zones/pexels_11798561.yaml: x 0.585–0.995, y 0.37–0.47 of 1280×720).
  const PLAN_PTS = '1010,110 1100,110 1100,610 1010,610'
  const CAM_PTS = '748.8,266.4 1273.6,266.4 1273.6,338.4 748.8,338.4'

  const setStep = (n) => steps.forEach((s, i) => {
    s.classList.toggle('is-active', i === n - 1)
    s.style.setProperty('--step-o', i === n - 1 ? 1 : 0.38)
  })

  function finalState() {
    gsap.set(photo, { opacity: 1 })
    gsap.set(plan, { opacity: 0 })
    gsap.set(label, { opacity: 0 })
    gsap.set(zone, { attr: { points: CAM_PTS }, fillOpacity: 0.18, drawSVG: '100%', stroke: '#e4f54a' })
    gsap.set(feet, { opacity: 1, scale: 1 })
    gsap.set(alert, { autoAlpha: 1, y: 0 })
    gsap.set(voices, { autoAlpha: 1 })
    steps.forEach((s) => { s.classList.add('is-active'); s.style.setProperty('--step-o', 1) })
    sec.classList.add('is-feed')
    stateEl.textContent = 'الكاميرا'
  }

  const mm = gsap.matchMedia()
  mm.add({ desktop: '(min-width: 961px)', reduce: '(prefers-reduced-motion: reduce)' }, (ctx) => {
    const { desktop, reduce } = ctx.conditions
    if (!desktop || reduce) { finalState(); return }

    sec.classList.remove('is-feed')
    gsap.set(sec, { backgroundColor: '#edefea', color: '#22262a' })
    gsap.set(photo, { opacity: 0 })
    gsap.set(plan, { opacity: 1, scaleY: 1, skewX: 0 })
    gsap.set(zone, { attr: { points: PLAN_PTS }, fillOpacity: 0, drawSVG: '0%', stroke: '#ff5b1f' })
    gsap.set('.p2c-line', { drawSVG: '0%' })
    gsap.set(['.p2c-grid', '.p2c-bubbles', '.p2c-cols', '.p2c-plan .north', label], { opacity: 0 })
    gsap.set(feet, { opacity: 0, scale: 0.4, transformOrigin: '50% 50%' })
    gsap.set(alert, { autoAlpha: 0, y: 16 })
    gsap.set(voices, { autoAlpha: 0 })
    stateEl.textContent = 'المخطط'
    setStep(1)

    const tl = gsap.timeline({ defaults: { ease: 'none' } })
    tl.to(['.p2c-grid', '.p2c-bubbles'], { opacity: 1, duration: 0.4 })
      .to('.p2c-line', { drawSVG: '100%', duration: 1, stagger: 0.12 }, '<')
      .to(['.p2c-cols', '.p2c-plan .north'], { opacity: 1, duration: 0.4 }, '-=0.4')
      .to(zone, { drawSVG: '100%', duration: 0.8 })
      .to(zone, { fillOpacity: 0.45, duration: 0.4 })
      .to(label, { opacity: 1, duration: 0.3 }, '<')
      .addLabel('project', '+=0.2')
      .to(sec, { backgroundColor: '#111517', color: '#d9dee0', duration: 0.8 }, 'project')
      .to(plan, { opacity: 0, scaleY: 0.55, skewX: -12, transformOrigin: '50% 60%', duration: 1 }, 'project')
      .to(label, { opacity: 0, duration: 0.3 }, 'project')
      .to(zone, { attr: { points: CAM_PTS }, fillOpacity: 0.18, stroke: '#e4f54a', duration: 1.1, ease: 'power1.inOut' }, 'project')
      .to(photo, { opacity: 1, duration: 0.9 }, 'project+=0.3')
      .addLabel('feet', '+=0.15')
      .to(feet, { opacity: 1, scale: 1, duration: 0.35, stagger: 0.25, ease: 'back.out(2)' }, 'feet')
      .addLabel('alert', '+=0.15')
      .to(alert, { autoAlpha: 1, y: 0, duration: 0.4 }, 'alert')
      .to(voices, { autoAlpha: 1, duration: 0.25, stagger: 0.18 })
      .to({}, { duration: 0.6 })

    const total = tl.duration()
    const at = (lbl) => tl.labels[lbl] / total
    ScrollTrigger.create({
      animation: tl, trigger: sec, start: 'top top', end: '+=340%',
      pin: true, scrub: 0.8, anticipatePin: 1,
      onUpdate: (self) => {
        const p = self.progress
        setStep(p < at('project') ? 1 : p < at('feet') ? 2 : p < at('alert') ? 3 : 4)
        stateEl.textContent = p < at('project') + 0.04 ? 'المخطط' : 'الكاميرا'
      },
    })
    return () => { sec.style.removeProperty('background-color'); sec.style.removeProperty('color') }
  })
})()

/* ------------------------------------------------------------------ S-03 schematic packets */
;(function schematic() {
  if (REDUCE) return
  const tl = gsap.timeline({ paused: true, repeat: -1, repeatDelay: 0.5 })
  const seq = [['a', 0], ['b', 0.75], ['c', 1.5], ['d', 1.5], ['e', 2.25]]
  seq.forEach(([k, t]) => {
    const pk = `#pk-${k}`
    const path = `#w-${k}`
    tl.set(pk, { opacity: 1 }, t)
      .to(pk, { motionPath: { path, align: path, alignOrigin: [0.5, 0.5] }, duration: 0.75, ease: 'none' }, t)
      .set(pk, { opacity: 0 }, t + 0.75)
  })
  loopWhenVisible(tl, '.schematic')
})()

/* ------------------------------------------------------------------ S-04 highlighter swipes */
if (!REDUCE) {
  $$('.hazards .hl').forEach((el) => {
    gsap.fromTo(el, { '--hl': '0%' }, {
      '--hl': '100%', duration: 0.7, ease: 'power2.out',
      scrollTrigger: { trigger: el, start: 'top 88%', once: true },
    })
  })
}

/* ------------------------------------------------------------------ S-05 pose skeletons */
const BONES = [['neck', 'shL'], ['neck', 'shR'], ['shL', 'elL'], ['elL', 'wrL'], ['shR', 'elR'], ['elR', 'wrR'],
  ['neck', 'pelvis'], ['pelvis', 'hipL'], ['pelvis', 'hipR'], ['hipL', 'knL'], ['knL', 'anL'], ['hipR', 'knR'], ['knR', 'anR']]
const standing = (ox) => ({
  head: [ox, 48], neck: [ox, 70], shL: [ox - 22, 78], shR: [ox + 22, 78], elL: [ox - 30, 118], elR: [ox + 30, 118],
  wrL: [ox - 34, 156], wrR: [ox + 34, 156], pelvis: [ox, 156], hipL: [ox - 12, 158], hipR: [ox + 12, 158],
  knL: [ox - 14, 206], knR: [ox + 14, 206], anL: [ox - 16, 252], anR: [ox + 16, 252],
})
const NS = 'http://www.w3.org/2000/svg'

function buildSkeleton(g, pose) {
  const lines = BONES.map(() => { const l = document.createElementNS(NS, 'line'); g.appendChild(l); return l })
  const joints = Object.keys(pose).filter((k) => k !== 'head').map((k) => {
    const c = document.createElementNS(NS, 'circle'); c.setAttribute('r', 4.5); g.appendChild(c); return [k, c]
  })
  const head = document.createElementNS(NS, 'circle'); head.setAttribute('r', 13); head.setAttribute('class', 'head'); g.appendChild(head)
  const render = (p) => {
    BONES.forEach(([a, b], i) => {
      lines[i].setAttribute('x1', p[a][0]); lines[i].setAttribute('y1', p[a][1])
      lines[i].setAttribute('x2', p[b][0]); lines[i].setAttribute('y2', p[b][1])
    })
    joints.forEach(([k, c]) => { c.setAttribute('cx', p[k][0]); c.setAttribute('cy', p[k][1]) })
    head.setAttribute('cx', p.head[0]); head.setAttribute('cy', p.head[1])
  }
  render(pose)
  return render
}
const mixPose = (a, b, t) => Object.fromEntries(Object.keys(a).map((k) => [k, [lerp(a[k][0], b[k][0], t), lerp(a[k][1], b[k][1], t)]]))

;(function sosTile() {
  const tile = $('#tile-sos')
  const bbox = $('.bbox', tile)
  const label = $('.bbox-label', tile)
  const alertP = $('.tile__alert', tile)
  const STAND = standing(160)
  const SOS = { ...STAND, elL: [124, 46], elR: [196, 46], wrL: [178, 14], wrR: [142, 14] }
  const render = buildSkeleton($('.skeleton', tile), STAND)
  const draw = (t) => {
    render(mixPose(STAND, SOS, t))
    bbox.setAttribute('y', lerp(22, 2, t)); bbox.setAttribute('height', lerp(244, 264, t))
  }
  const alarm = (on) => {
    bbox.classList.toggle('is-alert', on); label.classList.toggle('is-alert', on)
    label.textContent = on ? 'استغاثة #14' : '#14'; alertP.classList.toggle('is-on', on)
  }
  if (REDUCE) { draw(1); alarm(true); return }
  const st = { t: 0 }
  const tl = gsap.timeline({ paused: true, repeat: -1, repeatDelay: 0.6 })
  tl.call(() => { alarm(false); st.t = 0; draw(0) })
    .to({}, { duration: 0.9 })
    .to(st, { t: 1, duration: 0.9, ease: 'power2.inOut', onUpdate: () => draw(st.t) })
    .to({}, { duration: 0.45 })
    .call(() => alarm(true))
    .to({}, { duration: 2.4 })
    .call(() => alarm(false))
    .to(st, { t: 0, duration: 0.8, ease: 'power2.inOut', onUpdate: () => draw(st.t) })
  loopWhenVisible(tl, tile)
})()

;(function fallTile() {
  const tile = $('#tile-fall')
  const g = $('.skeleton', tile)
  const bbox = $('.bbox', tile)
  const label = $('.bbox-label', tile)
  const alertP = $('.tile__alert', tile)
  const timer = $('.tile__timer', tile)
  buildSkeleton(g, standing(120))
  const BOX_UP = { x: 70, y: 22, width: 100, height: 244 }
  // Lying pose = standing pose rotated 90° about the ankles (120, 252), lifted 24 units so the
  // lowest joint (the far wrist) rests on the ground line at y≈266 instead of sinking through it.
  const LIFT = -24
  const BOX_DOWN = { x: 96, y: 186, width: 252, height: 84 }
  const alarm = (on) => {
    bbox.classList.toggle('is-alert', on); label.classList.toggle('is-alert', on)
    label.textContent = on ? 'سقوط #09' : '#09'; alertP.classList.toggle('is-on', on)
  }
  const placeLabel = (box) => { label.setAttribute('x', box.x + box.width); label.setAttribute('y', Math.max(12, box.y - 6)) }
  if (REDUCE) {
    gsap.set(g, { rotation: 90, y: LIFT, svgOrigin: '120 252' })
    Object.entries(BOX_DOWN).forEach(([k, v]) => bbox.setAttribute(k, v)); placeLabel(BOX_DOWN)
    timer.textContent = '00:05'; alarm(true); return
  }
  const clock = { s: 0 }
  const tl = gsap.timeline({ paused: true, repeat: -1, repeatDelay: 0.6 })
  tl.call(() => {
    alarm(false); clock.s = 0; timer.textContent = '00:00'
    gsap.set(g, { rotation: 0, y: 0, svgOrigin: '120 252' })
    Object.entries(BOX_UP).forEach(([k, v]) => bbox.setAttribute(k, v)); placeLabel(BOX_UP)
  })
    .to({}, { duration: 1 })
    .to(g, { rotation: 90, y: LIFT, svgOrigin: '120 252', duration: 0.7, ease: 'power3.in' })
    .to(g, { rotation: 86, svgOrigin: '120 252', duration: 0.12, yoyo: true, repeat: 1, ease: 'power1.out' })
    .to(bbox, { attr: BOX_DOWN, duration: 0.3, onUpdate: () => placeLabel({ x: +bbox.getAttribute('x'), y: +bbox.getAttribute('y'), width: +bbox.getAttribute('width') }) }, '<')
    .to(clock, { s: 5, duration: 5, ease: 'none', onUpdate: () => { timer.textContent = `00:${pad(Math.floor(clock.s))}` } })
    .call(() => alarm(true))
    .to({}, { duration: 2.4 })
  loopWhenVisible(tl, tile)
})()

/* ------------------------------------------------------------------ S-06 risk index (illustrative data) */
;(function riskIndex() {
  // Illustrative values per zone for 06:00..18:00 (13 hourly points). Not real readings;
  // the page labels this section as an illustration.
  const SERIES = {
    A: [0.20, 0.25, 0.35, 0.45, 0.50, 0.55, 0.60, 0.58, 0.50, 0.45, 0.40, 0.30, 0.25],
    B: [0.15, 0.30, 0.45, 0.55, 0.62, 0.70, 0.66, 0.72, 0.68, 0.55, 0.45, 0.35, 0.25],
    C: [0.10, 0.35, 0.55, 0.65, 0.70, 0.80, 0.60, 0.65, 0.75, 0.70, 0.50, 0.30, 0.20],
    D: [0.10, 0.15, 0.20, 0.30, 0.35, 0.30, 0.25, 0.30, 0.35, 0.30, 0.20, 0.15, 0.10],
    E: [0.32, 0.40, 0.25, 0.20, 0.20, 0.25, 0.30, 0.25, 0.20, 0.25, 0.35, 0.45, 0.30],
    F: [0.10, 0.20, 0.40, 0.50, 0.55, 0.65, 0.70, 0.75, 0.60, 0.50, 0.40, 0.25, 0.15],
  }
  const NAMES = { A: 'الحفريات', B: 'حافة البلاطة', C: 'نطاق الرافعة', D: 'منطقة التشوين', E: 'المدخل', F: 'السقالات' }
  const LEVELS = [null, ['منخفض', '#cfe3c4'], ['متوسط', '#e4f54a'], ['مرتفع', '#ff9a5c'], ['حرج', '#dc2e26']]
  const levelOf = (v) => (v < 0.3 ? 1 : v < 0.5 ? 2 : v < 0.7 ? 3 : 4)
  const zones = $$('.zone').map((g) => ({ g, id: g.dataset.zone, rect: $('rect', g), lvl: $('.zone-level', g) }))
  const hourEl = $('#risk-hour')
  const topEl = $('#risk-top')
  const ruler = $('.ruler')

  function render(p) {
    const x = p * 12
    const i = Math.min(11, Math.floor(x))
    const f = x - i
    let top = null
    zones.forEach((z) => {
      const v = lerp(SERIES[z.id][i], SERIES[z.id][i + 1], f)
      const L = levelOf(v)
      z.rect.style.fill = LEVELS[L][1]
      z.lvl.textContent = LEVELS[L][0]
      z.g.classList.toggle('is-critical', L === 4)
      if (!top || v > top.v) top = { id: z.id, v }
    })
    const hours = 6 + x
    const hh = Math.floor(hours)
    const mm = Math.floor(((hours - hh) * 60) / 15) * 15
    hourEl.textContent = `${pad(hh)}:${pad(mm)}`
    topEl.textContent = NAMES[top.id]
    ruler.style.setProperty('--t', (p * 100).toFixed(2))
  }

  const mm = gsap.matchMedia()
  mm.add({ desktop: '(min-width: 961px)', reduce: '(prefers-reduced-motion: reduce)' }, (ctx) => {
    const { desktop, reduce } = ctx.conditions
    if (reduce) { render(7 / 12); return }
    render(0)
    const st = ScrollTrigger.create(desktop
      ? { trigger: '#risk', start: 'top top', end: '+=180%', pin: true, scrub: true, onUpdate: (s) => render(s.progress) }
      : { trigger: '#risk', start: 'top 70%', end: 'bottom 30%', scrub: true, onUpdate: (s) => render(s.progress) })
    return () => st.kill()
  })
})()

/* ------------------------------------------------------------------ S-07 evidence: scan-line reveal + bars */
$$('.scan').forEach((box) => {
  const img = $('img', box)
  const line = document.createElement('span')
  line.className = 'scan__line'
  box.appendChild(line)
  if (REDUCE) return
  gsap.set(img, { clipPath: 'inset(0% 0% 100% 0%)' })
  gsap.timeline({ scrollTrigger: { trigger: box, start: 'top 82%', once: true } })
    .set(line, { opacity: 1, top: '0%' })
    .to(img, { clipPath: 'inset(0% 0% 0% 0%)', duration: 1.1, ease: 'power1.inOut' })
    .to(line, { top: '100%', duration: 1.1, ease: 'power1.inOut' }, '<')
    .to(line, { opacity: 0, duration: 0.3 })
})

if (!REDUCE) {
  gsap.fromTo('.metrics .bar', { '--k': 0 }, {
    '--k': 1, duration: 1, stagger: 0.12, ease: 'power2.out',
    scrollTrigger: { trigger: '.metrics', start: 'top 82%', once: true },
  })
}

/* ------------------------------------------------------------------ S-09 programme (Gantt) */
;(function gantt() {
  const el = $('.gantt')
  const DAY = 864e5
  const start = new Date(2026, 9, 1)   // 1 Oct 2026
  const span = 80                       // 1 Oct → 20 Dec
  const t = ((Date.now() - start) / DAY / span) * 100
  const today = $('.gantt__today', el)
  if (t < 0 || t > 100) today.hidden = true
  else el.style.setProperty('--t', t.toFixed(2))
  if (REDUCE) return
  gsap.fromTo('.gantt__bar', { '--k': 0 }, {
    '--k': 1, duration: 0.8, stagger: 0.15, ease: 'power2.out',
    scrollTrigger: { trigger: el, start: 'top 78%', once: true },
  })
})()

/* ------------------------------------------------------------------ top bar: current sheet code
   Created last on purpose: ScrollTrigger measures in creation order, so these must come after
   the pinned sections (S-02, S-06) or their positions ignore the pin spacing. */
const sheetCode = $('#sheet-code')
$$('[data-sheet]').forEach((sec) => {
  // A pinned section's own box is one screen tall; its pin-spacer spans the whole pinned scroll.
  const box = sec.parentElement?.classList.contains('pin-spacer') ? sec.parentElement : sec
  ScrollTrigger.create({
    trigger: box, start: 'top 50%', end: 'bottom 50%',
    onToggle: (s) => { if (s.isActive) sheetCode.textContent = sec.dataset.sheet },
  })
})

/* Layout can shift once the web fonts arrive; re-measure every trigger then. */
document.fonts?.ready.then(() => ScrollTrigger.refresh())
