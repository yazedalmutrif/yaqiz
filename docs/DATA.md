# Data: the PPE detector v2 and the posture evaluation

Built and checked on 2026-10-07 (Asia/Riyadh). Every number in this file is copied from a script output, and the output file is named next to it. Nothing here was estimated.

> **Do not publish dataset images.** They show identifiable people, and some carry third-party marks. This also applies to the review sheets in `runs/ppe_v2/review/`. Use our own footage or the Pexels clips in the deck, the landing page and posts.

## 1. What each model needs

| Need | Where Yaqiz gets it |
|---|---|
| People, tracks, keypoints | COCO-pretrained YOLO11s + ByteTrack, and YOLO11s-pose (Ultralytics, used as released) |
| Helmet, head (a head without a helmet), vest | **PPE detector v2** (`models/ppe_v2.pt`, this file) |
| Machinery (for the machine-proximity rule) | **PPE detector v2** |
| Harness | **Not available.** No dataset could be used (section 6). The harness rule switches itself off when the model has no `harness` class, so it never raises false "harness missing" alerts. |
| Man-down and SOS | Keypoint geometry plus time, with no training. Man-down is evaluated on GMDCSA-24 (section 8). SOS is not evaluated yet: it needs staged clips (section 10). |

Unified classes of v2, in order: `helmet, head, vest, machinery` (`scripts/data_common.py`, `CLASSES`). The server maps classes **by name**, so a later model can add `harness` without code changes.

## 2. Training sources

All six sources have a permissive licence and download without an account. Each download is checked against a recorded checksum (`scripts/data_download.py`): the publisher's MD5 or SHA-256 for Harvard Dataverse, figshare, Hugging Face and Mendeley; for GDUT-HWD, which Google Drive publishes without one, the hash of our first download.

| Source (key) | What it is | Licence | Labels it provides | Images used: train / val / test |
|---|---|---|---|---|
| Hardhat (`hardhat_xie`) | Xie, L. (2019). *Hardhat.* Harvard Dataverse, V1. doi:10.7910/DVN/7CBGOS. Roboflow's "Hard Hat Workers" is a re-export of it. | CC0 1.0 | helmet, head | 4,392 / 470 / 1,766 |
| GDUT-HWD (`gdut_hwd`) | Wu J. et al. (2019). *Automatic detection of hardhats worn by construction personnel: A deep learning approach and benchmark dataset.* Automation in Construction 106, 102894. Data linked from github.com/wujixiu/helmet-detection. | Apache-2.0 (repository LICENSE) | helmet (4 colours), head (`none`) | 1,788 / 109 / 500 |
| CHVG (`chvg`) | Ferdous M., Ahsan S.M.M. (2022). *PPE detector: a YOLO-based architecture to detect personal protective equipment (PPE) for construction sites.* PeerJ Computer Science 8:e999. Data: doi:10.6084/m9.figshare.19625166.v1 | CC BY 4.0 | helmet, head, vest | 1,065 / 48 / 255 |
| RF100 construction-safety (`rf100_construction_safety`) | *construction-safety-gsnvb* (Roboflow 100, Ciaglia F. et al. 2022, arXiv:2211.13523), Hugging Face mirror | CC BY 4.0 | helmet, head (`no-helmet`), vest | 88 / 0 / 90 |
| RF100 excavators (`rf100_excavators`) | *excavators-czvg9* (Roboflow 100), originally "Excavators" by Mohamed Sabek | CC BY 4.0 | machinery (excavator, dump truck, wheel loader) | 2,314 / 142 / 96 |
| Korean site machinery (`kr_site_machinery`) | Na J., Shin H., Yun I., Lee J. (2025). *Development of an AI Dataset for Object Detection at Construction Sites.* Mendeley Data, V2. doi:10.17632/rz8723t6d7.2 | CC BY 4.0 | machinery (excavator, dump truck, bulldozer, crawler drill, crane, forklift) | 3,418 / 735 / 566 |

**Totals after de-duplication:** 13,065 training and 1,504 validation images (`data/datasets/ppe_v2/build_stats.json`). Test splits per source are listed in the table.

**Splits:**
- Hardhat: the official Train set is split into train/val (90/10, seed 0); the official Test set is the test split.
- GDUT-HWD: the official trainval is split 90/10. 500 images sampled from the official test list (seed 0) form the test split; the other official-test images go to train.
- CHVG: the release has no split, so a seeded random 75/10/15 split was used.
- RF100: the official splits. In the excavators set, every frame cut from the same 5 source videos goes to train.
- Korean site machinery: split **by recording date**. 2021-08-30 (foggy) and 2021-09-10 (sunny) are test, 2021-08-26 (foggy) is val, and the other dates are train.

**Class maps** (raw name → unified class; anything mapped to "dropped" is not used):
- Hardhat: helmet → helmet; head → head; person, others → dropped (persons are sparse: 616 boxes in 7,063 images).
- GDUT-HWD: blue, white, yellow, red → helmet; none → head.
- CHVG: white, yellow, blue, red → helmet; head → head; vest → vest; person, glass → dropped.
- RF100 construction-safety: helmet → helmet; no-helmet → head; vest → vest; person, no-vest, construction-safety → dropped.
- RF100 excavators: EXCAVATORS, dump truck, wheel loader → machinery.
- Korean site machinery: excavator, dumptruck, bull_dozer, crawler_drill, crane, fork_lift_truck → machinery; car → dropped. Boxes in the 4,719 frames used: dump truck 12,094, excavator 11,662, bulldozer 3,680, crawler drill 1,316, crane 133, forklift 16; 28,176 car boxes dropped (`data/datasets/ppe_v2/sources/kr_site_machinery/stats.json`).

**About the Korean archive:** Mendeley publishes one 9.37 GB file (SHA-256 `66f69e1c…c49c5a21`, matching the publisher's checksum). It is the **last part (disk 3 of 3) of a split ZIP**; parts 1 and 2 are not published. Its central directory is complete, so the 23,132 labelled frames stored in part 3 (8 recording dates, 2021-08-26 to 2021-09-13, 1920×1080, fixed site cameras) can be read with a ZIP reader that accepts the split-archive header (`data_download.read_split_last_part`). Consecutive video frames are nearly identical, so only every 5th frame of each clip is used (4,719 frames). Another 461 such frames (all from 2021-08-26, camera p01, the validation day) have their labels in an unpublished part of the archive and are skipped, so that day has 3 of its 4 cameras (`data_download.unpack_kr` now prints this count).

## 3. Evaluation-only data

| Data | Licence | Use |
|---|---|---|
| Ultralytics Construction-PPE, test split (141 images) | AGPL-3.0 | Comparing v1 and v2 on the same boxes. **Not used for training** because the licence is not permissive. See `DATASETS.md`. |
| GMDCSA-24 v2.1 (Alam E. et al. 2024; Zenodo doi:10.5281/zenodo.13354453) | The Zenodo record states CC BY 4.0; the repository's LICENSE file is MIT | 160 clips of 4 people at home (79 falls, 81 daily activities): evaluating the man-down posture rule (section 8). Indexed in `data/eval/falls/gmdcsa24_index.csv`. |

## 4. Merging sources that label different classes

Hardhat and GDUT label helmets and heads but not vests; the machinery sets label machines but not the workers' gear. Merging them as they are would teach the model that every unlabelled vest or machine is background. So the classes a source does not label are filled with **pseudo-labels** from teacher models, and every pseudo-label is checked before use.

1. **Two teachers**, trained only on permissively licensed sources that *do* label their classes. The Sprint 0 model is not used as a teacher because it was trained on AGPL-3.0 data.
   - **ppe teacher:** CHVG + RF100 construction-safety (1,153 train / 66 val images), YOLO11s, 60 epochs, 20.9 min. Validation: P 0.913, R 0.900, mAP50 0.929, mAP50-95 0.615 (`runs/ppe_v2/teacher_ppe.log`).
   - **machinery teacher:** RF100 excavators (2,315 train / 142 val images), YOLO11s, 40 epochs, 23.5 min. Validation: P 0.897, R 0.834, mAP50 0.904, mAP50-95 0.707 (`runs/ppe_v2/teacher_mach.log`).
2. **Expected pseudo-label quality.** Each teacher was scored on held-out test splits at confidence ≥ 0.5 and IoU ≥ 0.5 (`runs/ppe_v2/teacher_check.json`):

   | Teacher → test split | Class | Precision | Recall |
   |---|---|---|---|
   | ppe → CHVG | vest | 0.936 | 0.820 |
   | ppe → RF100 construction-safety | vest | 0.828 | 0.822 |
   | ppe → Construction-PPE | vest | 0.892 | 0.697 |
   | ppe → CHVG | helmet / head | 0.901 / 0.903 | 0.909 / 0.785 |
   | machinery → RF100 excavators | machinery | 0.942 | 0.792 |
   | machinery → Korean site machinery | machinery | 0.995 | 0.175 |

3. **Labelling.** Every train/val image of every source was run through the teacher(s) for the classes that source lacks. Boxes with confidence ≥ 0.5 were kept as pseudo-labels; test splits are never pseudo-labelled.
4. **Sanity filter** (`data_pseudolabel.py filter`; raw and filtered records are both kept in `data/datasets/ppe_v2/pseudo/`):
   - **Machinery pseudo-labels are not used at all.** The machinery teacher had only seen photos that contain machines. On the worker photos it put frame-sized "machinery" boxes over people and whole scenes: 2,720 boxes on Hardhat (2,545 of 4,862 train/val images), 878 on GDUT, 730 on CHVG, 49 on RF100 construction-safety. Every box on the 16-image review sheet `runs/ppe_v2/review/check_machinery_pseudo_hardhat_xie.jpg` was wrong.
   - **Gear must sit on a person.** A helmet/head pseudo-box is kept only if its centre lies in the head region of a person found by the COCO YOLO11s detector (conf ≥ 0.25, imgsz 960), and a vest only if it lies in the torso region. These are the same regions the live system uses (`yaqiz/vision/analysis.py`). This removed, for example, "helmets" on yellow loader buckets and dump-truck bodies (`runs/ppe_v2/review/check_dropped_by_person_filter_rf100_excavators.jpg`).

   | Source | Kept | Removed by the person check |
   |---|---|---|
   | Hardhat | vest 1,099 | vest 36 |
   | GDUT-HWD | vest 973 | vest 29 |
   | RF100 excavators | helmet 162, head 21, vest 141 | helmet 89, head 6, vest 25 |
   | Korean site machinery | none (its workers are too small for the teacher at conf ≥ 0.5) | – |

5. **Result.** Training split: original boxes helmet 23,748, head 7,482, vest 1,408, machinery 25,614; pseudo boxes vest 2,054, helmet 162, head 21. Validation split: original boxes helmet 1,898, head 541, vest 63, machinery 3,638; pseudo boxes vest 159 (`build_stats.json`).

**Known gaps:**
- Machines that appear in the worker photos stay unlabelled, so they count as background for those images.
- Workers in the Korean CCTV frames also stay unlabelled.
- Vests are the thinnest class.
- 94% of the validation split's machinery boxes come from one foggy day of the Korean site (3,430 of 3,638), so the best checkpoint is chosen mostly on that.
- Close-range machinery in training comes almost entirely from RF100 excavators (3,384 of 25,614 boxes).

## 5. Keeping test images out of training

- Test splits carry **original labels only**, and each source is scored **only on the classes it labels**.
- **Near-duplicates across all sources** (`scripts/data_dedupe.py`, `data/datasets/ppe_v2/dedupe.json`): a 64-bit difference hash of every image and of its mirror image, with pairs within 6 bits linked into groups. 20,657 images were hashed: 4,360 duplicate pairs in 1,802 groups, and 1,497 of those groups span two or more sources (web datasets re-use each other's photos).
  - A group that contains any test image (including the Construction-PPE test split) loses all its train/val members.
  - A group with only train/val members keeps one image.
  - Removed train + val images: Hardhat 435, GDUT 777, CHVG 331, RF100 construction-safety 1,028 (its images are video frames), RF100 excavators 103.
- **The Korean CCTV source is exempt within itself.** Every frame of a fixed camera looks alike to a coarse hash; with the rule above, 3,411 of its 3,418 training frames (and 734 of 735 validation frames) would have been dropped as "duplicates" of other days (`data_dedupe.py --link-within-all` → `runs/ppe_v2/dedupe_kr_within_check.json`). Its leakage control is the split by recording date. It is still checked against all the other sources. Its test frames come from held-out **days** of the **same cameras**, so they measure robustness to other days, weather and machine positions, not to new sites.

## 6. Checked and not used (2026-10-07)

| Dataset | Licence as published | Why it is not in v2 |
|---|---|---|
| SH17 (8,099 images, 17 classes) | CC BY-NC-SA 4.0 | Non-commercial (decided in Sprint 0, `DATASETS.md`) |
| MOCS (41,668 images, 13 classes) | CC BY-NC 4.0 | Non-commercial; access only by request form |
| ACID (10,000 images, 10 machine classes) | Custom terms: academic and research use only, no commercial use, no redistribution (acidb.net/term-of-use); CC BY-NC 4.0 in the OpenConstruction table | Non-commercial |
| AIDCON (2,155 drone images, 9 machine classes) | CC BY-NC 4.0 (OpenConstruction catalogue) | Non-commercial; access by request |
| SODA (19,846 images, 15 classes) | Not specified: "N/A" in the OpenConstruction table, "Not Specified" in its online catalogue; the paper gives no data licence | The download link in the paper returned HTTP 403 (Aliyun "AccessDenied") |
| Peru construction-site dataset (Del Savio A. et al. 2022, Data in Brief 42; 1,046 images at 3840×2160, 8 classes incl. tower crane, truck crane, concrete mixer truck, skid steer) | CC BY 4.0 (university repository record) | The ZIP host (oliva.ulima.edu.pe) sits behind a Cloudflare browser check (HTTP 403 for scripts, rechecked 2026-10-07). It can be downloaded in a browser ✍️ |
| Safety-harness dataset (Xu Z., Huang J., Huang K. 2023, IET Image Processing 17(4):1071–1085, doi:10.1049/ipr2.12696; 3,300 images) | Not specified: "N/A" in the OpenConstruction table, "Not Specified" in its online catalogue; the GitHub copy has no licence file | A public copy exists at github.com/Huangjiajing96/Dataset (3,300 images with VOC labels), but without a licence there is no permission to reuse it. Usable only with the authors' written permission ✍️ |
| SFCHD (12,373 images) | No licence file in its GitHub repository | No licence means no permission to reuse; the images also come from a chemical plant, not a construction site |
| SHEL5K (5,000 images, 6 classes) | CC BY 4.0 (Mendeley) | Mendeley names the Kaggle "hard-hat-detection" images as its source; not added in v2 ✍️ (candidate after an overlap check with Hardhat) |
| "Dataset of Personal Protective Equipment" (Mendeley zkzghjvpn2, 2025) | CC BY 4.0 | Its own method note says it was compiled from GitHub, Kaggle and Roboflow datasets plus the authors' own photographs, so the upstream licences of most images are unclear |
| "PPE Detection Dataset (5-Class)" (Mendeley 8vf7z6v5sb, 2025) | CC BY 4.0 | Not evaluated in this round ✍️ (candidate) |
| Roboflow Universe datasets (e.g. construction-site-safety) | Per dataset | The pages refuse automated requests (HTTP 403), and downloads need an account or API key |
| Person Detection on Construction Sites (Zenodo 14884208) | CC BY-SA 4.0 | Persons only; Yaqiz takes persons from the COCO model |

Sources for the catalogue entries: the OpenConstruction catalogue (doi:10.1061/JCCEE5.CPENG-7313; arXiv:2508.11482 v2, Table 4; openconstruction.org) and each dataset's own page, checked on 2026-10-07.

## 7. Results: PPE detector v2

**Training** (`runs/ppe_v2_metrics.json`, run folder `runs/train/ppe_v2_yolo11s-2/`):
- YOLO11s from COCO weights; 50 epochs (best epoch by Ultralytics' fitness: 42); imgsz 640, batch 32, seed 0, AMP; 82.3 min on the RTX 4070.
- Command: `python train_ppe_v2.py --epochs 50 --patience 12 --batch 32 --workers 8 --cache disk`.
- Weights: `models/ppe_v2.pt`, SHA-256 `5934c877…523abad2`.
- Validation at the best epoch (1,504 images; the validation vests include pseudo-labels): P 0.932, R 0.867, mAP50 0.938, mAP50-95 0.662.

**Held-out test results.** These use the Ultralytics validator (conf 0.001, IoU 0.7, imgsz 640). Test splits carry original labels only, and each source is scored only on the classes it labels.

| Test split | Class | Images | Boxes | P | R | mAP50 | mAP50-95 |
|---|---|---|---|---|---|---|---|
| Hardhat | helmet | 1,604 | 4,863 | 0.963 | 0.945 | 0.983 | 0.663 |
| Hardhat | head | 339 | 1,803 | 0.939 | 0.939 | 0.974 | 0.674 |
| GDUT-HWD | helmet | 465 | 2,671 | 0.911 | 0.812 | 0.867 | 0.525 |
| GDUT-HWD | head | 132 | 827 | 0.905 | 0.713 | 0.772 | 0.481 |
| CHVG | helmet | 216 | 539 | 0.884 | 0.939 | 0.937 | 0.575 |
| CHVG | head | 36 | 130 | 0.872 | 0.900 | 0.920 | 0.588 |
| CHVG | vest | 133 | 356 | 0.935 | 0.849 | 0.936 | 0.662 |
| RF100 construction-safety | helmet | 82 | 195 | 0.818 | 0.882 | 0.859 | 0.435 |
| RF100 construction-safety | head | 11 | 24 | 0.603 | 0.583 | 0.553 | 0.234 |
| RF100 construction-safety | vest | 57 | 129 | 0.847 | 0.853 | 0.871 | 0.459 |
| RF100 excavators | machinery | 95 | 144 | 0.950 | 0.833 | 0.904 | 0.697 |
| Korean site machinery (held-out days) | machinery | 566 | 3,238 | 0.892 | 0.805 | 0.863 | 0.620 |
| Construction-PPE (never trained on) | helmet | 110 | 192 | 0.831 | 0.766 | 0.748 | 0.272 |
| Construction-PPE (never trained on) | head | 24 | 40 | 0.168 | 0.250 | 0.143 | 0.029 |
| Construction-PPE (never trained on) | vest | 111 | 178 | 0.922 | 0.742 | 0.793 | 0.440 |

**Per class over all the training sources that label it:**

| Class | Boxes | P | R | mAP50 | mAP50-95 |
|---|---|---|---|---|---|
| helmet | 8,268 | 0.957 | 0.879 | 0.940 | 0.608 |
| head (no helmet) | 2,784 | 0.939 | 0.849 | 0.908 | 0.610 |
| vest | 485 | 0.910 | 0.850 | 0.916 | 0.594 |
| machinery | 3,382 | 0.895 | 0.808 | 0.867 | 0.624 |

Inference took 1.9–3.2 ms per image at 640, depending on the test split (validator, batch 32, RTX 4070).

**v1 (Sprint 0) vs v2 on the same test boxes** (mAP50):

| Test set | Class | v1 | v2 |
|---|---|---|---|
| Training sources combined | helmet | 0.589 | **0.940** |
| Training sources combined | head (no helmet) | 0.060 | **0.908** |
| CHVG + RF100 construction-safety | vest | 0.817 | **0.916** |
| Construction-PPE | helmet | **0.926** | 0.748 |
| Construction-PPE | head (no helmet) | **0.241** | 0.143 |
| Construction-PPE | vest | **0.903** | 0.793 |

How to read the comparison: **neither test is neutral.** The first three rows come from the test splits of v2's own training sources, which v1 never saw. The last three rows come from v1's own dataset, which v2 never saw. Each model is best on data like its training data. A fair verdict needs labelled footage that neither model has seen, ideally from our own sites ✍️.

**Sanity checks beyond mAP:**
- **Machinery on worker photos** (`scripts/eval_machinery_sanity.py` → `runs/eval/machinery_sanity.json`), at the live settings (conf 0.35, imgsz 960):
  - v2 put a machinery box on 17 of 1,766 Hardhat test images, 3 of 500 GDUT, 6 of 255 CHVG, 4 of 90 RF100 construction-safety and 0 of 141 Construction-PPE.
  - The 16 most confident of these boxes are almost all real machines in the background (`runs/eval/machinery_on_worker_photos_top16.jpg`).
  - For comparison, the machinery teacher fired on 70–76% of the same images (`runs/eval/machinery_sanity_teacher_mach.json`).
- **The proximity rule on real scenes:** people inside a cab are correctly not counted as "near" (`runs/eval/machine_proximity_examples.jpg`). v2 sometimes draws several boxes on one machine (body and bucket), so the live system keeps only the most confident box when one lies mostly inside another (`yaqiz/vision/engine.suppress_nested`, with a unit test).
- **The three demo clips** (6 frames per clip, live settings; `scripts/compare_v1_v2_clips.py` → `runs/eval/demo_clips_v1_vs_v2.json` and `.jpg`):
  - v2 finds more helmets (CAM-01: 41 vs 33; CAM-02: 32 vs 18).
  - v2 avoids v1's false "helmet" on a worker wearing a dark cap (CAM-03).
  - v2 finds **fewer vests on small, distant workers** (CAM-01: 14 vs 35; CAM-02: 11 vs 24). Lowering the vest threshold does not recover them: on CAM-01 only 5 more appear between 0.15 and 0.35. v2's vest examples are mostly close-ups. **Known limitation**; next step: label far-field vest examples from our own footage ✍️.

**Decision:** the live system uses v2 (`Settings.ppe_weights`; v1 remains the fallback file). It is far better on helmets and on heads without helmets (v1's weak point), it adds machinery, and it is trained only on permissively licensed data. With the default settings (vests required only in the laydown yard, which no calibrated camera covers), the vest gap raises no false alerts. With "vest required everywhere" switched on in Settings, as it was from 2026-10-07 13:36, it does: workers whose vests v2 misses are flagged as missing a vest on CAM-01 and CAM-02.

**First live run with v2** (2026-10-07 13:02):
- CAM-03 raised a helmet-missing alert for the worker in the dark cap, which v1 had called a helmet.
- CAM-01 raised two helmet-missing alerts that closed after 0.1 s. They are borderline: the rule had seen "no helmet" for 2 s, then the vote flipped back. They recur each time the demo clip loops (13 between 13:02 and 13:10).

## 8. Posture evaluation (GMDCSA-24)

`scripts/eval_posture.py` runs the same code as a camera worker: COCO YOLO11s + ByteTrack, YOLO11s-pose on every 2nd frame, `yaqiz.posture`, 10 processed frames per second. Output: `runs/eval/posture_gmdcsa24.json` and `.csv` (one row per clip). Two fall clips have no annotated fall interval and are excluded (Subject 4 Fall/09 and Fall/15), which leaves 77 fall clips and 81 daily-activity clips. The posture rule and the hold times were **not** tuned on this data; only the stillness tolerance of the full alert was chosen, on subjects 1–2 (below).

**Fallen posture** (the lying rule held for 0.5 s):

| | Result |
|---|---|
| Falls where the posture was recognised after the fall started | **63 of 77 (81.8%)** |
| By direction | sideways 25/28 (89.3%), forward 19/22 (86.4%), backward 19/27 (70.4%) |
| Time from the annotated fall start to recognition | median 1.42 s, 90th percentile 2.86 s, max 7.27 s |
| Fall clips with a false recognition before the fall | 6 |
| Daily-activity clips where the posture was flagged at some point | 43 of 81 (sleeping 13, exercising 7, sitting 5, standing 5, reading 2, walking 1, unlabelled moments 10) |

**The full man-down alert** (lying **and** still for 5 s): the clips end soon after the fall (median 3.96 s after the fall starts), so the alert can be scored only on the 11 fall clips that continue at least 6 s.

| Run | Alert on the 11 eligible falls | False alerts in 12.5 min of daily activity |
|---|---|---|
| Before the stillness fix (`runs/eval/posture_gmdcsa24_before_stillness_fix.json`) | 2 | 0 |
| After the fix, tolerance 0.25 (`runs/eval/posture_gmdcsa24_tol025.json`) | 3 | 2 (exercising on the floor; sleeping on a bed) |
| **Current code: tolerance 0.18** (`runs/eval/posture_gmdcsa24.json`) | **3** (subjects 1–2: 2 of 6; held-out subjects 3–4: 1 of 5) | **2** (the same two clips) |

**The stillness rule (2026-10-07).**
- **The bug.** On subject 2's clips, a motionless person on the floor was judged as "moving". The anchor point jumped between the torso centre (when keypoints were found) and the box centre (when they were not). The yardstick was 0.35 × box height, which is tiny for someone lying down.
- **The fix.** Stillness is now measured on the box centre in every frame, against 0.35 × the box's longer side. A regression test covers it (`tests/test_yaqiz_logic.py`).
- **The tolerance.** A code review showed that the first tolerance (0.25 of that yardstick) also accepted a lying worker who keeps moving in place. The tolerance was then chosen by a sweep on subjects 1–2 only (`eval_posture.py --sweep` → `runs/eval/posture_stillness_sweep.json`):
  - 0.08–0.10: 1 of 6 eligible falls caught, no false alert;
  - 0.12–0.15: 1 caught, 1 false alert (sitting);
  - 0.18–0.25: 2 caught, 1 false alert (exercising).
- **The choice.** 0.18 is the smallest value that keeps the higher catch rate. It rejects ±19 px in-place movement and a 20 px/s crawl on a 230 px body (`tests/test_yaqiz_review.py`), which 0.25 accepted. On all 160 clips, 0.18 flags exactly the same clips as 0.25. Subjects 3–4 were used for neither the diagnosis nor the choice.

**What this means:**
- The posture rule recognised 63 of 77 falls (82%): half of those within 1.42 s of the fall starting, and 49 of all 77 (64%) within 2 s.
- The 5-second alert is deliberately conservative. A person lying still in view (asleep on a bed, exercising on the floor) also meets it, so on a site, rest areas need their own rule ✍️. The hold time can be changed on S-08. GMDCSA-24 is indoor home footage; staged on-site clips are still needed (section 10).

## 9. How to reproduce

```powershell
cd C:\Users\yazed\Projects\SiteSafety
.venv\Scripts\python scripts\data_download.py          # downloads + checksum checks (no accounts)
.venv\Scripts\python scripts\data_convert.py           # unified YOLO labels per source
.venv\Scripts\python scripts\data_dedupe.py            # near-duplicate groups -> dedupe.json
.venv\Scripts\python scripts\data_pseudolabel.py teacher --which ppe
.venv\Scripts\python scripts\data_pseudolabel.py teacher --which mach
bash scripts/run_ppe_v2_pipeline.sh                    # check -> label -> filter -> build -> review -> train + evaluate
.venv\Scripts\python scripts\data_falls_index.py       # GMDCSA-24 index
.venv\Scripts\python scripts\eval_posture.py           # posture evaluation
```

## 10. Still needed from Yazeed ✍️

1. **Harness data:** this is the missing class. Pick one:
   - a free Roboflow account, then export a harness dataset whose own licence allows our use. The API key goes in an environment variable, never in a file.
   - ask Xu, Huang and Huang (IET Image Processing 2023) for written permission, or a licence, to use the public copy at github.com/Huangjiajing96/Dataset (3,300 images, VOC labels).
   - film and label our own: 300–500 images of team members with and without a harness at height, with everyone's consent, labelled with a free tool.
2. **The Peru dataset:** download it in a browser from `https://oliva.ulima.edu.pe/dspace_dataset/Dataset-Object-identication-training-construction.zip` and save it to `data\datasets\_downloads\`. It adds tower cranes, truck cranes and concrete mixer trucks.
3. **Staged clips for SOS and man-down:** 10–20 of each, filmed from a raised phone (2–4 m) on a site or yard, with everyone's consent. For man-down, the person should stay still on the ground for at least 10 s; for SOS, cross both arms above the head for 2–3 s.
4. **Optional:** ask the authors of the Korean dataset whether parts 1 and 2 of the archive can be published.
5. **A native speaker** to check the Urdu, Hindi and Bengali voice phrases.
