# Yaqiz (يقظ): landing page

This is the one-page Arabic (RTL) website for Yaqiz, our team's entry to the IECE 2026 Engineering Hackathon (Track 3, «سلامة مواقع البناء»). It runs fully offline: the fonts are self-hosted, so it works at the venue without internet.

## Run it
```powershell
cd C:\Users\yazed\Projects\SiteSafety\site
npm install        # first time only
npm run dev        # live editing at http://localhost:5173
npm run build      # production files in dist\
npm run preview    # serve dist\ at http://localhost:4173
```

## Design
The page reads as an **engineering drawing set marked up by an HSE engineer**:
- Graphite linework on cool drafting paper.
- Highlighter-yellow zones and red revision clouds.
- Each section is a numbered "sheet" with a title block, and the top bar shows the current sheet code.

Where the story moves to the cameras, the page switches to a **dark CCTV feed**.

- Typefaces: Changa (headings, signage feel) and IBM Plex Sans Arabic (text), via @fontsource.
- Motion: GSAP 3 (ScrollTrigger, DrawSVG, MotionPath) plus Lenis smooth scroll.

| Sheet | Motion |
|---|---|
| S-00 hero | Live site plan: the crane jib turns, workers move, and one enters the excavation. A revision cloud and an alert follow. |
| S-01 problem | The statement reveals word by word with scroll (never split below word level, which would break Arabic joining). Counters count up. |
| S-02 plan to camera | **Pinned and scrubbed.** The plan draws itself and the HSE zone is drawn. The zone then morphs onto the real prototype frame, exactly where the prototype's zone sits (`configs/zones/pexels_11798561.yaml`). Foot-point rings appear, then the multilingual alert. |
| S-03 how it works | Packets travel along the single-line schematic. |
| S-04 hazards | Highlighter swipe on each hazard. |
| S-05 the worker | Pose-skeleton loops: an SOS with crossed arms, and a fall followed by a 5-second timer and an alert. |
| S-06 risk index | **Pinned and scrubbed.** The 06:00→18:00 shift recolours the zones, with the midday-ban band shown. *Illustrative data, labelled on the page.* |
| S-07 prototype | Scan-line reveal of the real screenshots; mAP bars fill. |
| S-09 programme | The Gantt bars draw, and the "today" line is computed from the current date. |

- **Reduced motion:** every animation has a static end state, and it is used when the OS asks for reduced motion.
- **Paused loops:** loops stop when off screen or when the tab is hidden.

## Facts on the page
- Statistics, rules and the comparison table come from the fact-checked deck. The sources are in `Claude Brain\11 Agents\Outputs\2026-10-06 Yaqiz - Evidence Pack.md` and are listed in the page's «المراجع».
- Prototype numbers (S-05, S-07) are copied from `..\runs\ppe_v2_metrics.json`, `..\runs\eval\live_20261007_130326.json` and `..\runs\eval\posture_gmdcsa24.json` (measured on 2026-10-07; details in `..\docs\DATA.md`). The CAM-A/B/C screenshots are from Sprint 0 (2026-10-06, `..\runs\zone_demo_*.log`), and `img\dashboard-plan.webp` is the live dashboard (S-02 site plan) on 2026-10-07.

## Before publishing online
1. ✍️ Fill in Reem's and Abdullah's full names, majors and roles, and the contact line (S-10 in `index.html`).
2. ✍️ Have the alert phrases in Urdu, Hindi and Bengali (S-02) checked by native speakers.
3. Brand marks in the footage are blurred in `public\img\` ("ICON" on a vest in `detector.webp`, and vest lettering in `zone-pour-area.webp`). The originals in `..\docs\screenshots\` are untouched.
4. Run an independent fact-check of the page text.
5. Ask Yazeed before deploying anywhere (GitHub Pages and Cloudflare Pages both work with `dist\`).
