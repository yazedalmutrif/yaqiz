# Media sources

The three demo clips come from **Pexels** and were downloaded on 2026-10-06. They are used only to run the demo (inference). They are **never used to train a model**.

**How they were downloaded:** on 2026-10-06 the clips were fetched with `curl` from each page's public download link, using a browser User-Agent. The Pexels Terms of Service (https://www.pexels.com/terms-of-service/, section 8) forbid "the use of programs or robots for automatic data collection", so that was not the right way to do it. From now on, download clips by hand with the page's **Free download** button, or use the official Pexels API with the key kept in an environment variable. `scripts/get_videos.py` no longer downloads anything; it only checks that the files exist and that their SHA-256 matches the table below.

**Pexels licence** (https://www.pexels.com/license/, checked 2026-10-06): all photos and videos are free to use, attribution is not required, and modification is allowed. Not allowed:
- identifiable people "may not appear in a bad light or in a way that is offensive";
- implying endorsement of your product by the people or brands in the footage;
- selling unaltered copies (posters, prints, physical products);
- redistributing or reselling on other stock platforms;
- using the content as part of a trade mark, design mark, trade name, business name or service mark.

Because our overlays label people "IN DANGER ZONE" / "NO HELMET", we:
- picked footage where faces are **not** clearly identifiable (high angle, far away, or from behind);
- print a footer on every annotated zone-demo frame: *"Demo zone drawn for illustration; stock footage, no real violation implied."* The zones are ours, not real site rules.

| File (data/videos/) | Pexels page | Creator | Uploaded | As downloaded | SHA-256 | Used for |
|---|---|---|---|---|---|---|
| `pexels_35631533.mp4` | https://www.pexels.com/video/construction-workers-on-building-site-35631533/ | SÀI GÒN CÔNG TY CP SẢN XUẤT - THƯƠNG MẠI | 2026-01-12 | 2160x3840 (portrait), 29.97 fps, 26.1 s | `d1865af00a9d...46421` | Zone demo, clip 1 |
| `pexels_11798561.mp4` | https://www.pexels.com/video/workers-on-construction-11798561/ | manas patra | 2022-04-13 | 1280x720, 50 fps, 9.7 s (the page lists 1920x1080; the file served was 1280x720) | `fcce622402a6...41dce` | Zone demo, clip 2 |
| `pexels_5434223.mp4` | https://www.pexels.com/video/workers-walking-in-construction-site-5434223/ | Everett Bumstead | 2020-09-24 | 1920x1080, 23.98 fps, 24.1 s | `df2f645caad8...2fa4` | PPE detector still (workers seen from behind) |

Full hashes are in `scripts/get_videos.py`.

## Brand marks in the footage ✍️

- **Clip 1:** a "DELTA" word mark is clearly readable on the vest of a worker flagged `IN DANGER ZONE` in the annotated MP4 and in frames such as `frame_00400.png` and `frame_00460.png`. **Blur it before any public use of the MP4 or those frames.** Screenshot `01_zone_pour_area.png` is fine: there the mark is hidden by rebar.
- **Clip 3:** an "ICON" word mark is visible in screenshot `03_ppe_detector.png`. That screenshot shows no violation, but blur the mark or decide it is acceptable before the PDF goes out.

## Rejected candidates

These were downloaded the same way and are kept only in `data/videos_candidates/` (git-ignored; safe to delete):
- Pexels 14054967, 14058343 and 35025682: drone shots, people too small.
- 5423610: a single worker with a moving camera.
- 9227135 and 11733685: identifiable faces.
- 8964930: only two people, standing still.
- 9226051: close-up through a mesh; the person is identifiable.
