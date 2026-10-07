# Yaqiz (يقظ): construction-site safety system

**What:** a safety layer for construction sites that runs on the site's existing cameras or on phones used as cameras. The HSE engineer draws danger zones once on the site plan. Yaqiz then watches every calibrated camera and:
- raises alerts on the dashboard and through the site speaker in five languages;
- logs every violation and near-miss with a blurred snapshot;
- turns the log into a risk index per zone and hour, and a printable daily HSE report in Arabic.

**Why:** IECE 2026 Engineering Hackathon (Saudi Council of Engineers), Track 3, challenge «سلامة مواقع البناء». Team leader: Yazeed Almutrif.

**Stack:**
- Python 3.10, FastAPI + WebSockets, SQLite (SQLModel)
- Ultralytics YOLO11 (detection, pose) + ByteTrack, OpenCV, Shapely
- React 19 + TypeScript + Vite (Arabic, right-to-left) and GSAP

Everything runs locally on one RTX 4070 PC, with no cloud service.

## What it detects

| Event | Rule | Severity |
|---|---|---|
| Danger-zone entry | A worker's foot point is inside an active no-entry zone (drawn on the plan, mapped to each camera by a homography) for 3 frames; escalates to critical after 10 s inside | warning → critical |
| Missing PPE | Helmet missing (an explicit "head without helmet" detection), or vest missing where required, by majority vote over recent frames, held for 2 s | warning |
| Worker down | Lying posture (from keypoints, or the box shape) **and** still, held for 5 s | critical |
| SOS gesture | Both wrists raised above the shoulders and **crossed**, held for 1.5 s | critical |
| Midday heat ban | A worker in an outdoor zone during the summer midday ban (15 Jun – 15 Sep, 12:00–15:00) | warning |
| Close to machinery | A worker within about one body height of a detected machine, on the ground (needs a model with a `machinery` class) | warning |

All thresholds can be changed in the dashboard (S-08). Zones can be switched on and off by work phase (for example "crane operating"), and a zone can send a **simulated** interlock signal to the equipment operator. A real machine stop is out of scope until an engineer signs it off.

**Privacy:** faces are pixelated in every saved snapshot, and in the live stream by default. Processing stays on the site PC, and worker IDs are temporary tracker numbers, not identities.

## Run it (demo day)

```powershell
cd C:\Users\yazed\Projects\SiteSafety
# one-time setup (needs internet): see "Install" below
.venv\Scripts\python -m yaqiz seed --reset   # demo site: plan, 5 zones, 3 demo cameras (clears the event log)
.venv\Scripts\python -m yaqiz serve          # then open http://127.0.0.1:8000
```

| Sheet | What the operator does there |
|---|---|
| S-01 Live monitoring | Camera tiles, live alerts, KPIs, critical banner, site-speaker toggle |
| S-02 Site plan | Live worker positions from calibrated cameras, alert clouds, today's heat map |
| S-03 Zones | Draw and edit zones on the plan; set the kind, the PPE required, outdoor, interlock |
| S-04 Camera calibration | Click ≥ 4 matching ground points on the plan and in the camera image (use 6+ so the error can be checked) |
| S-05 Log | Filter, acknowledge, export CSV |
| S-06 Risk index | Zone × hour grid with heat weighting; manual heat entry when offline |
| S-07 Daily report | Print to PDF from the browser (Arabic shaping stays correct) |
| S-08 Settings | Cameras (RTSP, HTTP, a phone camera app, webcam `0`, or a video file), voice languages, thresholds, site location |

**Offline check:**
- The models (`models/*.pt`), the voice clips (`app/public/voices/`) and the built dashboard (`app/dist`) are all local.
- Only the weather lookup needs the internet; when offline, enter the temperature and humidity by hand on S-06.
- Before the demo, start the server once and check that every camera tile shows a picture.

**Develop the dashboard:** `cd app; npm install; npm run dev` (http://localhost:5174; it proxies `/api` and `/voices` to the server). Run `npm run build` before using port 8000.

## Run it on another PC (Windows)

1. Unzip `Yaqiz-source-2026-10-07.zip` anywhere.
2. Install Python 3.10 (python.org) if the PC does not have it.
3. Double-click `setup_windows.bat`. This is one-time and needs internet: it installs PyTorch and the packages, then builds the demo site.
4. Double-click `run_dashboard.bat`. The dashboard opens at http://127.0.0.1:8000.
5. Double-click `run_landing.bat`. The landing page opens at http://127.0.0.1:4180.

**Requirements:** an NVIDIA GPU gives the real speed; without one, Yaqiz still runs, but slowly.

**Demo clips are not included.** Either:
- download them by hand from the Pexels links in `MEDIA_SOURCES.md` into `dataideos\`, then run `.venv\Scripts\python -m yaqiz seed --reset`; or
- add a webcam (source `0`) or a phone camera on the Settings page.

## Run it on a Mac

**Needs:** an Apple Silicon Mac (M1 or newer) with macOS 14 Sonoma or newer. The PyTorch version Yaqiz uses has no build for Intel Macs. Yaqiz uses the Mac's GPU (Apple MPS).

1. Unzip `Yaqiz-source-2026-10-07.zip`.
2. Install Python 3.10–3.13 from python.org if the Mac does not have it.
3. Open **Terminal**, type `cd ` (with a space), drag the unzipped `Yaqiz` folder into the window and press Enter.
4. Run `bash setup_mac.command`. This is one-time and needs internet.
5. Run `bash run_dashboard.command`. The dashboard opens at http://127.0.0.1:8000.
6. To see the landing page, run `bash run_landing.command` in a second Terminal window. It opens http://127.0.0.1:4180.

The `.command` files can also be opened with a double-click. macOS blocks downloaded scripts the first time; allow them in System Settings → Privacy & Security → "Open Anyway", or run `xattr -dr com.apple.quarantine .` once in the folder.

**Demo clips are not included** (see `MEDIA_SOURCES.md`). You can also add the Mac's camera (source `0`) on the Settings page.

## Measured results

All numbers are copied from the files named; full tables are in `docs/DATA.md`.

- **Live speed** (`scripts/measure_live.py` → `runs/eval/live_20261007_130326.json`):
  - 3 cameras at once on one RTX 4070 (the three demo clips played as camera feeds), each at a median of 10.0 FPS (the cap).
  - From a frame being decoded to its events being published: median 78–79 ms, worst 95th percentile 141 ms.
  - Each rule's confirmation time comes on top (for example 3 frames for a zone entry).
- **PPE detector v2** (`models/ppe_v2.pt`; helmet, head without helmet, vest, machinery), trained on six permissively licensed datasets:
  - On held-out test splits, mAP50 is 0.940 for helmet, 0.908 for head without a helmet, 0.916 for vest and 0.867 for machinery.
  - v1 scored 0.589 / 0.060 / 0.817 on the same helmet / head / vest boxes. On v1's own Construction-PPE test set v1 is better, so neither comparison is neutral.
  - v2 also misses vests on small, distant workers (`docs/DATA.md`, section 7).
- **Man-down posture** on the GMDCSA-24 fall clips (`docs/DATA.md`, section 8):
  - The fallen posture was recognised in 63 of 77 falls, with a median of 1.42 s after the fall starts.
  - The full 5-second alert could only be scored on 11 fall clips, because the others end too soon. It fired on 3.
  - It gave 2 false alerts in 12.5 minutes of daily activity (someone lying on a bed, someone exercising on the floor).
- **Sprint 0** (first detector and zone demo): see the report below.

## Repo layout

```
yaqiz/         the system: config, geometry (homography), posture, rules, heat, risk, store (SQLite),
               voice, interlock, report, vision/ (camera workers, models, analysis, overlay, privacy), api/
app/           dashboard (React + TypeScript + Vite), Arabic RTL; built into app/dist and served by yaqiz
site/          landing page (Vite + GSAP), see site/README.md
scripts/       data pipeline (data_*.py, train_ppe_v2.py, run_ppe_v2_pipeline.sh), eval_posture.py,
               and the Sprint 0 scripts
core/          Sprint 0 modules (kept for the Sprint 0 scripts)
configs/       bytetrack_site.yaml (tracker), zones/ (Sprint 0)
tests/         pytest suite (`.venv\Scripts\python -m pytest -q`)
docs/          SPEC.md (the system spec), DATA.md (data and model), screenshots/
HANDOFF.md     status and the prompt to continue the work
data/ models/ runs/ weights/ .ultralytics/   (not in git: datasets, clips, weights, outputs)
```

## Install

```powershell
py -3.10 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu130
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest -q
cd app; npm install; npm run build; cd ..
.venv\Scripts\python -m yaqiz voices      # only if app\public\voices is empty (needs internet once)
```

No system CUDA toolkit is needed: the PyTorch wheel ships its own CUDA runtime, so only the NVIDIA driver is required. No API keys or secrets are used.

## Licences

- **Code:** Ultralytics is AGPL-3.0, so treat this repo as AGPL-3.0 unless an Ultralytics Enterprise licence is bought. There is no LICENSE file yet; add one before publishing anything ✍️.
- **Data:** see `docs/DATA.md` (PPE v2 training sources, all permissive) and `DATASETS.md` (Sprint 0: Construction-PPE, AGPL-3.0, now used for evaluation only).
- **Clips:** Pexels licence; see `MEDIA_SOURCES.md` (download by hand, blur brand marks before public use).

---

## Sprint 0 report (2026-10-06)

> Sprint 0 proved the two core building blocks before the full system existed: a PPE detector (YOLO11s fine-tuned on Construction-PPE) and a danger-zone check (ByteTrack + foot point in a polygon). The code is in `core/` and the Sprint 0 scripts. The name lives in `PROJECT_NAME` in `core/config.py` for those scripts.

### Results (Sprint 0, measured 2026-10-06 on an RTX 4070)

All numbers below were copied from the script output. Logs: `runs/train_ppe_yolo11s_e100.log`, `runs/eval_test.log`, `runs/zone_demo_*.log`.

#### Training

| Setting | Value |
|---|---|
| Base model | `yolo11s.pt` (COCO-pretrained) |
| Data | Construction-PPE train 1,132 / val 143 / test 141 images, 11 classes |
| imgsz / batch / optimizer | 640 / 16 / AdamW (picked by Ultralytics `optimizer=auto`, lr 0.000667) |
| Epochs | 100 requested, patience 30. **Early stop after 80 epochs; best epoch 50** |
| Seed | 0, `deterministic=True`, AMP on, images cached in RAM (Ultralytics warns that RAM caching can make reruns differ slightly) |
| Wall-clock | **682.9 s (11.4 min)**, including setup and final validation |

#### Detector accuracy on the held-out **test** split (141 images, best.pt, imgsz 640)

Copied from `scripts/eval_ppe.py --split test`:

```
                 Class     Images  Instances      Box(P          R      mAP50  mAP50-95)
                   all        141       1251      0.614      0.544      0.556      0.271
                helmet        110        192       0.96      0.906      0.926      0.484
                gloves         75        163      0.822      0.755      0.783      0.388
                  vest        111        178      0.863      0.865      0.903      0.582
                 boots         75        211      0.789      0.645      0.722      0.381
               goggles         51         52      0.817      0.827      0.857      0.341
                  none         35         65      0.503      0.554      0.446      0.134
                Person        133        236      0.808      0.805      0.817       0.49
             no_helmet         24         40      0.418      0.275      0.241     0.0721
             no_goggle         24         33      0.505      0.216      0.303     0.0753
             no_gloves         23         58      0.276      0.138     0.0958     0.0252
              no_boots          6         23          0          0     0.0231    0.00411
```

Read it like this: **helmet (mAP50 0.926) and vest (0.903) are strong**. The `no_*` classes are weak; `no_helmet` is 0.241 mAP50 on only 40 test boxes. All 24 test images that carry `no_helmet` labels were checked by eye, and none of them is a construction site: they are general photos of people (portraits, sport, offices, concerts). So `NO HELMET` on real site footage is **not reliable yet**.

(Validation split at the end of training, best.pt: all P 0.669, R 0.543, mAP50 0.581, mAP50-95 0.281; helmet 0.836 / 0.426; vest 0.818 / 0.502; no_helmet 0.374 / 0.12.)

#### Zone demo speed (two YOLO11s models + ByteTrack + Shapely + overlay, imgsz 960)

| Clip | Frames | Processed at | Processing FPS (after 10 warm-up frames) | Processing FPS (all frames) | End-to-end FPS (incl. decoding and downscaling the source video and writing MP4 + PNGs) |
|---|---|---|---|---|---|
| Pexels 35631533 (4K portrait source) | 781 | 1080x1920 | **41.53** | 38.51 | 16.85 |
| Pexels 11798561 (720p source) | 486 | 1280x720 | **46.52** | 40.65 | 30.99 |

"Processing FPS" times both models, tracking, zone logic and drawing per frame; it is the number shown in the overlay header. The end-to-end figure is lower, likely because the 4K source is decoded and downscaled on the CPU and every frame is re-encoded (not profiled separately). When a screenshot is used in the PDF, caption it with both numbers.

#### Screenshots

| File | What it shows |
|---|---|
| `docs/screenshots/01_zone_pour_area.png` | Clip 1, frame 700 (t=23.4 s): worker #111 inside the "Pour area" polygon flagged `IN DANGER ZONE`; three workers outside flagged OK (#82 helmet; #1 and #5 helmet + vest, boxes shown) |
| `docs/screenshots/02_zone_slab_edge.png` | Clip 2, frame 150 (t=3.0 s), static camera on an upper slab: three workers (#1, #3, #5) flagged in the "Slab edge (east)" zone; three others OK; one far-left worker `PPE ?`. Some workers behind the parapet are not detected |
| `docs/screenshots/03_ppe_detector.png` | Raw PPE detector output (helmet, vest, Person with confidences) on workers seen from behind, clip 3 at t=10 s |

#### Known issues (Sprint 0)

- **No `NO HELMET` example on real footage.** The logic is built and unit-tested, but nobody in the chosen clips was detected without a helmet, and the `no_helmet` class is weak (see above).
- **Missed person inside the zone (most important).** In clip 1 the worker in the blue DELTA vest is crouched among the column bars inside the "Pour area" and has **no person box in any saved frame from 550 to 680** (about 4 s at 29.97 fps). His next `zone_entry` is at frame 665 (#107). So for roughly 3.5-4 s a worker inside the zone raised no alert. Cause: the COCO person detector loses a crouched worker behind dense vertical bars.
- **ID switches.** ByteTrack gave 49 IDs on the portrait clip and 36 on the slab clip, while the header shows 5-13 people per saved frame in clip 1 and 5-11 in clip 2. Causes: workers hidden behind rebar and parapets, and the 0.30 person threshold, which removes the low-score boxes that ByteTrack's second matching pass is meant to use. A rerun with `--person-conf 0.10` (`runs/zone_demo_conf010/*/fps.json`) gave 47 and 37 IDs (16 events instead of 13 on clip 2) and more duplicate boxes, so 0.30 was kept. A new ID restarts the 3-frame entry check, so one worker can raise several `zone_entry` events: the worker in the blue DELTA vest appears under several IDs, e.g. #37, #75 and #111.
- **Missed dark helmet.** In `03_ppe_detector.png` the right-hand worker's dark hard hat (partly behind a broom) is not detected. There are also duplicate `Person` boxes on that worker in the same frame.
- **Zones are in image pixels.** Clip 1 is a slowly moving aerial shot, so the zone drifts relative to the ground. Sprint 1 should map zones from the site plan with a homography.
- **Two detectors per frame** (COCO person model for tracking + PPE model). This is simpler and more robust today, but it costs speed.
- **Far, small people** often stay `PPE ?` because the dataset is mostly close-up images.
- **No harness class** in this dataset.
- Ten training label files have no matching image (1,142 labels vs 1,132 images); Ultralytics ignores them.
- **Brand marks:** "DELTA" is readable on a flagged worker in the clip-1 MP4 and some of its frames, and "ICON" is visible in screenshot 03. Blur both before public use (see `MEDIA_SOURCES.md`) ✍️.
- **How the clips were fetched:** on 2026-10-06 they were downloaded with `curl` and a browser User-Agent, which the Pexels Terms of Service do not allow for automated collection. Download them again by hand (or through the official API) before anything is published.
- **Overwrite guards:** `train_ppe.py` and `eval_ppe.py` now refuse to overwrite the published weights or metrics without `--force`. These guards were added after the measured runs. The current `models/ppe_yolo11s_best.pt` is byte-identical to `runs/train/ppe_yolo11s_e100/weights/best.pt`.

### How Sprint 0 worked

```
video frame ─┬─> YOLO11s (COCO, class "person") ─> ByteTrack ─> person boxes + IDs ─┐
             └─> YOLO11s (fine-tuned PPE) ─> helmet / no_helmet / vest boxes ───────┤
                                                                                   v
     PPE box -> person (head region for helmets, torso for vests)
     helmet: majority vote over the last 15 frames per ID; vest: per frame (can flicker)
     foot point (bottom-centre) -> Shapely polygon test (3 frames to enter, 5 to leave)
                                                                                   v
                         overlay + MP4 + PNG frames + events.json + fps.json
```

- Zones are YAML files in `configs/zones/`, with points normalised to 0..1, so one file works at any resolution.
- `zone_entry` is logged each time a person ID is confirmed entering a zone (3 frames in; 5 frames out to clear). `no_helmet` is logged once per ID. Nothing is logged per frame.
- Person detections (conf >= 0.30) go to ByteTrack with a 60-frame lost-track buffer (`configs/bytetrack_site.yaml`).

### Sprint 0 files

```
core/          config.py (name, paths), zones.py, ppe.py, rules.py, overlay.py
scripts/       check_gpu.py, get_dataset.py, get_videos.py, train_ppe.py, eval_ppe.py,
               zone_demo.py, detect_frame.py
configs/       zones/ (one YAML per demo clip), bytetrack_site.yaml (tracker settings)
tests/         unit tests (geometry, PPE association, per-track rules)
docs/screenshots/  curated annotated PNGs
DATASETS.md    dataset, licence, source
MEDIA_SOURCES.md   video clips, licence, creators
data/ models/ runs/ weights/ .ultralytics/   (git-ignored: dataset, clips, weights, outputs,
               Ultralytics settings; weights/yolo26n.pt comes from Ultralytics' AMP self-check)
```

### Re-run Sprint 0 (Windows, PowerShell, from the repo root)

```powershell
py -3.10 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu130
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\check_gpu.py          # expects "cuda ok True"
.venv\Scripts\python -m pytest -q tests

.venv\Scripts\python scripts\get_dataset.py        # 178 MB download (~350 MB on disk) into data\datasets\, hash-checked
# Download the 3 clips by hand from the Pexels pages in MEDIA_SOURCES.md (Free download button),
# save them as data\videos\pexels_<id>.mp4, then check them:
.venv\Scripts\python scripts\get_videos.py         # verifies the files and their SHA-256
.venv\Scripts\python scripts\train_ppe.py --epochs 100 --model yolo11s.pt
.venv\Scripts\python scripts\eval_ppe.py --split test

.venv\Scripts\python scripts\zone_demo.py --video data\videos\pexels_35631533.mp4 --zones configs\zones\pexels_35631533.yaml --show-ppe
.venv\Scripts\python scripts\zone_demo.py --video data\videos\pexels_11798561.mp4 --zones configs\zones\pexels_11798561.yaml --show-ppe
.venv\Scripts\python scripts\detect_frame.py --video data\videos\pexels_5434223.mp4 --time 10
```

No system CUDA toolkit is needed: the PyTorch wheel ships its own CUDA runtime. Only the NVIDIA driver is required.
Ultralytics keeps its settings in `.ultralytics/` inside this repo (`YOLO_CONFIG_DIR`, set in `core/config.py`), and the scripts switch off its anonymous usage telemetry (`sync=False`).
Note: before that change, the first runs on 2026-10-06 created `%APPDATA%\Ultralytics\settings.json` and `Arial.ttf`. That global settings file now has `sync: false` and `datasets_dir` pointing into this repo. Delete it if you want Ultralytics defaults back elsewhere.
No API keys or secrets are used.
