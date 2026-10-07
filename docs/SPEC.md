# Yaqiz (يقظ) product spec v1: the real system

The source of truth for what we build. If the code and this file disagree, fix one of them on purpose and record the decision in `HANDOFF.md`.

## 1. What it does
Yaqiz runs on the site's existing cameras (or phones used as IP cameras) and on one GPU PC on site. It:

1. **Detects** people (COCO detector + tracking, with pose keypoints), PPE (helmet, head without helmet, vest) and machinery. Harness waits for training data.
2. **Understands the site.** Zones are drawn once **on the site plan**. Each camera is calibrated to the plan with a homography (≥4 point pairs), so every zone is projected into every camera, and every worker's foot point is projected back onto the plan, where live positions are shown.
3. **Responds:**
   - an alert to the supervisor dashboard (WebSocket)
   - a multilingual voice alert (Arabic, English, Urdu, Hindi, Bengali) on the site speaker
   - an equipment-operator signal (simulated; MQTT when configured)
4. **Anticipates.** Every event is logged (SQLite) with a face-blurred snapshot. The log feeds a **risk index per zone per hour**, a heat/midday-ban monitor, and an **Arabic daily HSE report**.

## 2. Event types
| kind | trigger (defaults in Settings) | severity |
|---|---|---|
| `zone_intrusion` | the foot point is inside an **active** `no_entry` zone for ≥ `enter_frames`; escalates to critical after `escalate_s` | warning → critical |
| `ppe_missing` | a person in a zone (or anywhere, with site rules on) lacks a required item for ≥ `ppe_hold_s`. Items: helmet, vest, harness (harness only if the model has the class) | warning |
| `man_down` | posture is lying (torso within 30° of horizontal from keypoints, or a box much wider than tall without them) **and** the person stays still (box centre moves < 0.18 × 0.35 × the box's longer side over 2 s; `posture.STILL_TOL`, chosen in `docs/DATA.md` §8) for ≥ `man_down_s` | critical |
| `sos` | both wrists are above the shoulders **and** crossed (wrist order flipped relative to shoulder order) for ≥ `sos_hold_s` | critical |
| `midday_exposure` | the midday ban is active (15 Jun–15 Sep, 12:00–15:00 Asia/Riyadh) and a person is inside an `outdoor` zone | warning |
| `machine_proximity` | a person's foot point is on the ground within `machine_gap` body heights of a machinery box: sideways, and in depth within the band from the machine's ground line up to 60% of its height (`vision/analysis.near_machine`); ignored: the operator (mostly inside the machine's box, feet above 35% of its height, at most half its height) and anyone more than 6× smaller than the machine (far behind it); a lying worker is measured by body length. Debounced like zones; needs the machinery class | warning |

Events carry a per-(track, kind) cooldown, store their duration, and can be acknowledged.

## 3. Architecture
```
SiteSafety/
  yaqiz/                 Python package (backend + vision engine)
    config.py            settings (pydantic-settings, YAQIZ_* env vars, .env)
    db.py, models.py     SQLModel + SQLite (WAL) tables: Site, Zone, Camera, Event, StatMinute, Setting
    geometry.py          homography fit/project, polygon tests, foot points
    posture.py           SOS + man-down state machines from COCO keypoints
    rules.py             zone/PPE rules → debounced, cooled-down event candidates
    heat.py              heat index (NWS), categories, midday ban, Open-Meteo fetch with cache
    risk.py              risk index per zone × hour, levels 1–4
    report.py            daily report aggregation
    voice.py             phrase catalogue (5 languages) + edge-tts generation
    interlock.py         simulated / MQTT operator signal
    vision/              sources.py (file/RTSP/HTTP/webcam, latest-frame reader), engine.py (pose+track, PPE),
                         analysis.py (association, zones, posture), privacy.py (face blur from keypoints),
                         overlay.py (stream annotations), worker.py (camera thread)
    bus.py               thread → asyncio fan-out to WebSocket clients
    api/                 FastAPI app factory + routers (site, zones, cameras, calibration, events, risk,
                         report, heat, settings, streams, ws); serves app/dist as the SPA
    seed.py              demo site: generated plan + the 3 Pexels clips as cameras, calibrated, with zones
    __main__.py          `python -m yaqiz serve | voices | seed`
  app/                   React + TypeScript + Vite dashboard (Arabic RTL)
  site/                  landing page (done)
  tests/                 pytest (geometry, posture, rules, heat, risk, API)
  scripts/               Sprint 0 + data/training scripts
  data/ (git-ignored)    datasets, videos, snapshots, yaqiz.db, site/plan.png
  models/                weights (ppe_yolo11s_best.pt now; ppe_v2.pt after the data work)
```

**Threading.** Each camera has a reader thread (it always keeps only the latest frame) and a worker thread:
- **Per camera:** the pose model, used for tracking (Ultralytics `track(persist=True)` keeps per-model state).
- **Shared:** the PPE detector, behind a lock.
- **Throttling:** each camera is capped at `max_fps`.

**Events.** Workers write events to SQLite in short sessions, then publish to `bus` with `loop.call_soon_threadsafe`.

## 4. API (prefix `/api`)
- `GET /health`
- `GET|PUT /site`, `POST /site/plan` (image), `GET /site/plan`
- `GET|POST /zones`, `PUT|DELETE /zones/{id}`
- `GET|POST /cameras`, `PUT|DELETE /cameras/{id}`, `POST /cameras/{id}/start|stop`
- `GET /cameras/{id}/frame.jpg` (raw, face-blurred), `GET /cameras/{id}/stream.mjpg` (annotated)
- `PUT|DELETE /cameras/{id}/calibration` with body `{pairs:[{plan:[x,y], image:[u,v]}…]}`; returns the homography and the reprojection error
- `GET /events?since&until&kind&zone_id&camera_id&limit&offset`, `POST /events/{id}/ack`, `GET /events/{id}/snapshot.jpg`
- `GET /risk?date=YYYY-MM-DD`, `GET /report?date=`, `GET /heat`, `PUT /heat/manual`, `GET|PUT /settings`
- `WS /ws` message types:
  - `event` (new or updated)
  - `stats` (per camera: fps, people, in_zone, ppe ok/bad)
  - `positions` (per camera: tracks in plan coordinates)
  - `camera_status`
  - `heat`

## 5. Dashboard (Arabic RTL)
The design carries the landing-page identity: a drawing set on paper for the plan, log, risk and report pages, and a dark camera feed for live monitoring. Fonts are Changa and IBM Plex Sans Arabic, and each sheet has a code.

| Sheet | Page | Answers |
|---|---|---|
| S-01 | المراقبة الحية | Is the site safe now? Camera tiles, alert feed (ack, voice), status strip (people, in-zone, PPE %, cameras online, heat) |
| S-02 | مخطط الموقع | Where is everyone? Plan with zones, live worker dots, revision clouds on active alerts, event heatmap |
| S-03 | المناطق | Zone editor: draw/edit polygons on the plan; kind, PPE requirements, active, outdoor, interlock |
| S-04 | معايرة الكاميرات | Pick ≥4 point pairs plan ↔ camera; homography; preview of projected zones on the frame |
| S-05 | السجل | What changed? Filterable events, snapshots, acknowledge, CSV export |
| S-06 | مؤشر الخطر | Where is the risk? Zones × hours grid, heat/midday panel, top zones |
| S-07 | التقرير اليومي | Printable Arabic HSE report (browser "Save as PDF") |
| S-08 | الإعدادات | Cameras, voice languages, thresholds, privacy, site location |

Motion is functional only:
- an alert card arrives
- a revision cloud draws around the zone on the plan
- counters update

Reduced motion is respected.

## 6. Data and models (owned by the data workstream; see `docs/DATA.md`)
- **PPE detector v2:** classes `helmet, head, vest, machinery` (no harness yet: no usable data). Six permissively licensed sources; label-set mismatches handled with filtered pseudo-labels. Persons do **not** come from this model. Full record: `docs/DATA.md`.
- **Persons and keypoints:** `yolo11s.pt` + ByteTrack for people, `yolo11s-pose.pt` for keypoints (COCO, AGPL-3.0). SOS and man-down are geometric rules plus time persistence, so they need no training data. Man-down is evaluated on public fall clips (GMDCSA-24, `docs/DATA.md` §8); staged on-site clips are still needed for both.

## 7. Non-negotiables
- No invented numbers. Every metric shown is measured, and illustrative data is labelled.
- **Privacy:** faces are blurred in stored snapshots (always) and in streams (setting, on by default). No identities are stored, only track IDs.
- No secrets in code. Keys go in `.env` (git-ignored).
- The server binds to `127.0.0.1` unless `YAQIZ_HOST` is set.
- The Arabic UI is RTL, with LTR isolates for codes and numbers. Arabic text is never split below word level.
