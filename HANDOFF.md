# HANDOFF: continue building Yaqiz (read this first)

**Where:** `C:\Users\yazed\Projects\SiteSafety\`. Hand-over folder for Yazeed (2026-10-07): `C:\Users\yazed\Projects\Yaqiz-2026-10-07\` (`START HERE.html`, launchers, model, results, docs copies, built landing page, source zip). Full spec: `docs/SPEC.md`. Data and model notes: `docs/DATA.md`. Landing-page notes: `HANDOFF-CHATGPT.md` and `site/README.md`.

## Prompt to continue (paste into a new Claude Code session opened in this folder, or into ChatGPT along with the files it needs)
> You are continuing the Yaqiz project for Yazeed Almutrif: an AI construction-site safety system for the IECE 2026 Engineering Hackathon (Track 3). Read `HANDOFF.md` and `docs/SPEC.md` in `C:\Users\yazed\Projects\SiteSafety\`, then continue from the first unchecked item in "Status" below.
>
> Work like a senior engineer and UI/UX designer:
> - small verified steps
> - run `.venv\Scripts\python -m pytest -q` after backend changes
> - run `npm run build` in `app\` after frontend changes
>
> Never invent numbers: copy them from script output, and mark unknowns with ✍️. Ask before anything that leaves the computer (deploys, posting, accounts). Update this file's Status before you stop.

## Status (update as you go)
- [x] Sprint 0: PPE detector v1 (YOLO11s on Construction-PPE), zone demo, measured results (`README.md`)
- [x] Landing page `site\` (browser-verified 2026-10-07; updated with v2 and posture results and fact-checked, see below).
- [x] Spec (`docs/SPEC.md`)
- [x] Backend `yaqiz/`:
  - geometry (homography + calibration coverage clipping), posture (SOS / man-down), rules (hysteresis, cooldown, de-dup), heat (NWS heat index + midday ban + Open-Meteo), risk, store (SQLite WAL, aware UTC)
  - vision: COCO YOLO11s + ByteTrack for people, YOLO11s-pose every 2nd frame matched by IoU, PPE model every 2nd frame, face pixelation from keypoints
  - **machine proximity (2026-10-07):** `vision/analysis.near_machine` (image-space, scaled by the worker's height; ignores the operator in the cab) + rule 5 in `rules.py` + "NEAR MACHINE" overlay + voice phrase `machine_*` + setting `machine_gap`. It is active only when the PPE model has a `machinery` class (v2).
  - day-shift risk grid = 06:00–17:59 (12 columns; was off by one)
- [x] Tests: 57 passing (`.venv\Scripts\python -m pytest -q`)
- [x] Voice clips: 35 files in `app/public/voices/` (7 phrases × 5 languages). ✍️ The ur/hi/bn phrases need a native-speaker check.
- [x] Dashboard `app\` S-01 … S-08, browser-verified 2026-10-07 at 958 px wide (Monitor, Plan, Zones editor, Calibration, Log, Risk, Report, Settings). Fixes: header wrap, table scroll, camera codes in the log, bidi of LTR phrases, flex table cell, 4-point calibration note.
- [x] Posture evaluation on GMDCSA-24 (`scripts/eval_posture.py` → `runs/eval/posture_gmdcsa24.json/.csv`; full write-up in `docs/DATA.md` §8):
  - fallen posture recognised in 63/77 falls (81.8%), median 1.42 s after the annotated fall start
  - full man-down alert (down and still 5 s): fired on 3 of the 11 clips long enough to score it, and 2 false alerts in 12.5 min of daily activity (sleeping, exercising)
  - **stillness bug fixed 2026-10-07** (`yaqiz/posture.py`: anchor = box centre in every frame, yardstick = 0.35 × the box's longer side) + regression test; diagnosed on subjects 1–2 only, subjects 3–4 held out. The pre-fix run is kept in `runs/eval/posture_gmdcsa24_before_stillness_fix.json`.
  - ✍️ idea: a "rest area" zone kind where man-down is suppressed (a person sleeping in view meets the rule)
- [x] **PPE v2 trained** (2026-10-07, 50 epochs, 82.3 min; `models/ppe_v2.pt`, metrics in `runs/ppe_v2_metrics.json`, full write-up in `docs/DATA.md` §7):
  - held-out mAP50 (training sources' test splits): helmet 0.940, head 0.908, vest 0.916, machinery 0.867
  - v1 is better on its own Construction-PPE test set (helmet 0.926 vs 0.748), so neither comparison is neutral
  - v2 misses vests on small distant workers (demo clip CAM-01); a lower vest threshold does not fix it → label far-field vests ✍️
  - pseudo-labels: machinery pseudo-labels dropped (the teacher fired on 69–76% of worker photos); gear pseudo-labels must sit on a detected person (`data_pseudolabel.py filter`)
  - machinery on worker photos at live settings: 17/1,766 Hardhat test images, mostly real machines (`runs/eval/machinery_sanity.json`)
- [x] Server restarted on v2 (2026-10-07 13:00); the 3 demo cameras are running again. Live measurement: 10.0 FPS median per camera, capture → processed latency median 78–79 ms, p95 ≤ 141 ms (`scripts/measure_live.py` → `runs/eval/live_20261007_130326.json`); latency shows on each camera tile.
- [x] Browser check with v2: Monitor, Plan (live dots and clouds), overlays (helmet/vest tags, zones, pixelated faces). First live helmet-missing alerts (CAM-03: worker in a dark cap, correct; CAM-01: two 0.1 s borderline alerts).
- [x] Overlay: nested machinery boxes merged (`vision/engine.suppress_nested`, tested).
- [x] Landing page `site\` updated (S-05 SOS/fall status + GMDCSA-24 result, S-07 v2 results + live speed + dashboard screenshot, S-08 key, S-09 programme). Before-copy: `runs/site_index_before_status_update.html`. Rebuilt; preview with `cd site; npx vite preview --port 4173`.
- [x] **fact-checker** (2026-10-07): PASS WITH FIXES on `docs/DATA.md`, README (top) and the landing-page changes. All 24 fixes applied. The main ones:
  - the harness dataset is NOT MIT; a public copy without a licence exists at github.com/Huangjiajing96/Dataset, so ask the authors;
  - SODA's licence is not specified;
  - fall timing stated precisely;
  - SOS marked as not evaluated;
  - the latency wording says "from decode on the PC";
  - the full Construction-PPE numbers are on the page;
  - the fall caption separates posture from the full alert.
- [x] **code review** (2026-10-07). Fixes applied, with tests in `tests/test_yaqiz_review.py`:
  - the camera thread survives any failing frame and shows "stalled" or "error";
  - events left open by a killed server are closed at startup;
  - de-duplication no longer merges two workers standing side by side, and its radius scales with person size;
  - near_machine: stricter operator test, scale-plausibility check, a lying worker measured by body length;
  - the frame source returns frame + timestamp in one read;
  - stale filtered pseudo-labels are refused;
  - the daily report's risk table covers 24 h;
  - Arabic number agreement in counts.
- [x] **Man-down stillness tolerance = 0.18** (was 0.25), chosen by a sweep on GMDCSA-24 subjects 1–2 only (`runs/eval/posture_stillness_sweep.json`). It rejects in-place movement (±19 px, a 20 px/s crawl). On all 160 clips it flags the same clips as 0.25 (`docs/DATA.md` §8).
- [ ] Review items left open:
  - a pixel-motion or keypoint-speed cue for man-down;
  - longer carry-over for machine events hidden by the machine;
  - a validation split that is not 94% one foggy Korean day (`docs/DATA.md` §7 notes it);
  - `scripts/compare_v1_v2_clips.py` and `eval_machinery_sanity.py` assume a GPU.
- [ ] ✍️ **Yazeed's settings (saved from the dashboard at 13:36):**
  - "vest required everywhere" is ON, and voices are Arabic + English only.
  - With v2 weak on distant vests, the vest setting produces many false "no vest" alerts on CAM-01/CAM-02.
  - Suggest turning it off until far-field vest labels exist. Your call: it was left as you set it.
- [ ] Machine proximity has not been seen live: none of the 3 demo clips shows machinery. Download by hand (Pexels "Free download", not a script) a clip with workers near an excavator, add it as a camera, and check the events ✍️
- [ ] Next data work: far-field vest labels; a neutral test set labelled from our own footage; harness data; staged SOS / man-down clips (`docs/DATA.md` §10)
- [ ] Idea: a "rest area" zone kind where man-down is suppressed (a person lying still on purpose meets the rule)
- [ ] Before demo day: `python -m yaqiz seed --reset` (clears the event log), check every camera tile, fact-check the deck

## How to run
```powershell
cd C:\Users\yazed\Projects\SiteSafety
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m yaqiz seed --reset   # demo site, plan, 3 demo cameras, zones (clears the event log)
.venv\Scripts\python -m yaqiz serve          # http://127.0.0.1:8000
# dashboard dev: cd app; npm install; npm run dev  (http://localhost:5174, proxies /api and /voices)
```

## Data workstream in one paragraph
Six permissively licensed, no-login sources (`scripts/data_common.py` holds the registry with licences and attributions): Hardhat (Xie, CC0), GDUT-HWD (Apache-2.0), CHVG (CC BY 4.0), RF100 construction-safety and RF100 excavators (CC BY 4.0), and the Korean construction-site machinery dataset (Na et al., Mendeley rz8723t6d7 v2, CC BY 4.0). Mendeley publishes only the LAST part of that split ZIP, so only the 23,132 frames stored in part 3 are readable; every 5th frame is used and the split is by recording date. Sources label different classes, so two teacher models (PPE on CHVG + RF100 construction-safety; machinery on RF100 excavators) fill the missing classes with pseudo-labels at conf ≥ 0.5; test splits keep original labels only and are scored only on the classes each source labels. Near-duplicates are removed across sources (dHash); the CCTV source is exempt within itself because its date split is its leakage control. Construction-PPE (AGPL-3.0) is evaluation-only (v1 vs v2). No usable harness dataset exists without an account or a request, so v2 has no harness class (the harness rule stays off).

## Decisions log
- 2026-10-07: people are tracked with the COCO YOLO11s detector + ByteTrack (a pose-only tracker found 1 of 7–8 workers on CAM-01); keypoints come from YOLO11s-pose matched by IoU. The PPE model detects gear and machinery only.
- 2026-10-07: SOS and man-down are keypoint geometry plus time persistence (no training data). Evaluated on GMDCSA-24; staged team clips still needed ✍️.
- 2026-10-07: zones live in plan coordinates; cameras are calibrated with a homography; live worker positions are shown on the plan.
- 2026-10-07: the daily report is printed from the browser (correct Arabic shaping), not generated server-side.
- 2026-10-07: machine proximity is image-space and scaled by the worker's height (no metric calibration needed); it is a warning-level near-miss and does not know whether the machine is running.
- 2026-10-07: posture thresholds were NOT tuned on GMDCSA-24, so its numbers stay an honest held-out measurement.
