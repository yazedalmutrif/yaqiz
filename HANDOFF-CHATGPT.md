# Handoff prompt for ChatGPT (copy everything below the line)

Status as of 2026-10-07: **website build in progress** (this file is updated at the end of each work block; see "Current status").

---

You are continuing a project for me, Yazeed Almutrif (يزيد سلطان المطرف), a CS graduate from Taif University in 2026. Reply to me in the language I write in.

## The project
**Yaqiz (يقظ)** is an AI construction-site safety system. It's my team's entry to the **IECE 2026 Engineering Hackathon**, run by the Saudi Council of Engineers as part of the 4th International Engineering Conference. We're in Track 3 «الابتكار الهندسي», challenge «سلامة مواقع البناء».

The team is Yazeed (team leader), Reem ✍️ and Abdullah ✍️. Their surnames, majors and roles are still unknown, so **don't invent them**.

- Tagline: «موقع ينبّه قبل الحادث.. بدلًا من كاميرا تكتفي بتسجيله»
- Closing line: «يقظ.. لأن كل عامل يستحق أن يعود إلى بيته سالمًا»

## Folders on my PC
- **Prototype (Python):** `C:\Users\yazed\Projects\SiteSafety\`. The folder name is historical; the project is Yaqiz.
  - Results are in `README.md`, the screenshots in `docs\screenshots\`, and the venv in `.venv\`.
- **Website:** `C:\Users\yazed\Projects\SiteSafety\site\`. Vite + vanilla JS + GSAP (ScrollTrigger) + Lenis.
  - Run: `cd site` → `npm install` → `npm run dev` → open http://localhost:5173
  - Build: `npm run build`, which outputs to `site\dist\`.
- **Obsidian notes:** `C:\Users\yazed\OneDrive\Desktop\Claude Brain\02 Projects\Yaqiz\Yaqiz.md`, plus the evidence pack and deck prompt in `11 Agents\Outputs\2026-10-06 Yaqiz - *.md`.

## Website spec
- **Language and layout:** Arabic, `dir="rtl" lang="ar"`, one page.
- **Typefaces:** IBM Plex Sans Arabic for text, IBM Plex Mono for technical labels and numbers. Both are self-hosted via @fontsource so the site works offline at the venue.
- **Palette:** charcoal `#0E1117` / `#111827`, safety orange `#F97316`, hi-vis yellow `#FACC15`, alert red `#EF4444`, text `#E5E7EB`, muted `#94A3B8`. A thin blueprint grid sits behind dark sections.
- **Look:** an engineering blueprint crossed with a hi-vis safety vest. Labels look like a detection HUD (monospace, boxes, coordinates).
- **Motion:**
  - GSAP ScrollTrigger, scrub-linked and pinned sections, with Lenis for smooth scroll.
  - **Never split Arabic text into letters**; it breaks letter joining. Split by words only.
  - Respect `prefers-reduced-motion`: show everything static.
  - In RTL, horizontal scrolling moves toward the left visually (later items sit further left).

**Sections in order:**
1. **Hero:** an animated top-down site plan. Cameras sweep, the crane jib rotates, workers move, and one walks into the excavation zone. It turns red, ripples, and an alert card pops up. Tagline and buttons sit beside it.
2. **Statement:** «الكاميرات موجودة.. لكنها تسجّل ولا تنبّه», revealed word by word as you scroll.
3. **Problem:** counters that count up as they come into view (sources are in "Facts" below).
4. **Pinned "from plan to camera"** (the signature visual): the blueprint draws itself, danger zones get drawn, the plan tilts into the camera's perspective (homography), detection boxes appear, and one box turns red.
5. **How it works:** a pipeline from cameras → on-site processing → rules engine → alerts + event log → risk index, with a light packet travelling along the path.
6. **Hazards:** 5 cards (falls, struck-by/suspended loads, excavation, missing PPE, heat stress), plus a line naming the OSHA Fatal Four (names only).
7. **The worker** (dark section): an animated stick figure crosses its arms for SOS, and a falling figure triggers an alert after N seconds.
8. **Risk index:** a zone heatmap scrubbed across a shift from 06:00 to 18:00, with the midday-ban band from 12:00 to 15:00 highlighted. **Labelled «بيانات توضيحية».**
9. **Prototype:** real screenshots plus the measured metrics below, revealed with a scan-line effect.
10. **Comparison table** (exact rows below).
11. **Horizontal timeline.**
12. **Team.**
13. **Closing, sources list and disclaimer.**

## Facts (use only these; never invent numbers)
- **GOSI 2023:** 27,133 work injuries across all sectors, 7,413 of them from falls. Source: GOSI via Okaz, March 2024.
- **BLS:** 1,032 deaths in US construction and extraction occupations in 2024, 370 of them from falls, slips and trips. Source: BLS, Feb 2026.
- **ILO:** 2.93 million deaths a year from work accidents and occupational disease. Source: ILO 2023 report (2019 data).
- **Midday ban:** 12:00–15:00 from 15 Jun to 15 Sep, applying to all private-sector establishments. The ministry *calls on* employers to provide shade, rest and awareness (it is not a stated legal duty). Source: HRSD.
- **NCOSH:** runs an e-service for reporting work incidents, injuries and near-misses (ncosh.gov.sa).
- **Building code:** SBC 201-2024, Chapter 33, safeguards during construction.
- **PDPL:** Arts. 11, 13 and 18 (minimum data, notice of purpose, destruction).
- **Prototype, measured 2026-10-06 on an RTX 4070:**
  - YOLO11s fine-tuned on the Ultralytics Construction-PPE dataset (AGPL-3.0; 11 classes; train 1,132 / val 143 / test 141 images).
  - Training took 682.9 s (11.4 min). It stopped early after 80 epochs; the best epoch was 50.
  - **Held-out test set (141 images), mAP50:** helmet 0.926, vest 0.903, goggles 0.857, person 0.817, gloves 0.783, boots 0.722. **Across all 11 classes: 0.556** (the `no_*` classes are weak, e.g. no_helmet 0.241).
  - **Full pipeline speed** (two models + ByteTrack + zone check + overlay): **41.5–46.5 FPS** processing after warm-up.
  - The screenshots use Pexels stock footage. The zones are drawn for illustration, and no real violation is implied.

**Comparison table rows.** Columns are manual patrols | traditional CCTV | existing AI safety platforms | Yaqiz (proposed design):
- رصد لحظي للمخالفات: جزئيًا | لا | ✔ | ✔
- مناطق خطر تُرسم على مخطط الموقع الهندسي: لا | لا | جزئيًا | ✔
- مؤشر خطر لكل منطقة مبني على الحوادث الوشيكة: لا | لا | جزئيًا | ✔
- نداء استغاثة بإشارة من العامل مع رصد السقوط: لا | لا | جزئيًا | ✔
- تنبيه صوتي في الموقع بعدة لغات: جزئيًا | لا | جزئيًا | ✔
- ربط الإجهاد الحراري برصد العمل المكشوف بالكاميرا وقت حظر الظهيرة: لا | لا | جزئيًا | ✔
- جاهزية تجارية ونشر في مواقع فعلية: لا ينطبق | ✔ | ✔ | نموذج أولي

Under the table: «✔ = ضمن تصميم يقظ؛ المنفّذ في النموذج الأولي الحالي: رصد معدات الوقاية ومناطق الخطر». Footnote: «المقارنة مبنية على المواد المنشورة لمنصات مثل viAct وIntenseye وProtex AI (تاريخ الاطلاع: 6 أكتوبر 2026)، وعدم ظهور ميزة في موادها لا يعني غيابها».

## Rules
- Never claim "nobody else does this".
- "Warns", not "prevents".
- Use «مطوّر الذكاء الاصطناعي», not «مهندس» (a professional title the SCE grants).
- The equipment signal goes to the operator, and is simulated for now.
- Don't use the logos of the SCE, the conference or any real company.
- Mark anything unknown with ✍️.

## Current status (update this when you finish something)
- [x] Site scaffolded (Vite 8, GSAP 3.15, Lenis 1.3, @fontsource Changa and IBM Plex Sans Arabic)
- [x] All sections built (sheets S-00 to S-10 plus the closing). The design is an engineering drawing set, switching to a dark camera feed.
- [x] Verified in Chrome at 1440×900 on 2026-10-07: no console errors or warnings; the pinned sequences, sheet indicator, counters, Gantt "today" line and scan reveals all work.
- [ ] Mobile layout: the CSS breakpoints are written, but not yet checked on a phone.
- [ ] Reduced-motion path: the code is written, but not yet checked with the OS setting on.
- [ ] ✍️ Reem's and Abdullah's details and the contact line, in `index.html` S-10.
- [ ] ✍️ A native-speaker check of the Urdu, Hindi and Bengali alert lines in S-02.
- [ ] Not deployed. Ask Yazeed first.

## What I want from you now
Continue from "Current status". If I attach files from `site\` (index.html, src\main.js, src\styles.css), edit them and give me back complete files, not fragments. Keep every fact exactly as listed above.
