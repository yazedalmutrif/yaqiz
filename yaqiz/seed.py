"""Demo site: a generated site-plan drawing, five zones and three demo cameras (Pexels clips),
calibrated so the plan zones land exactly on the zones used in Sprint 0 (configs/zones/*.yaml)."""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
from sqlmodel import SQLModel

from .config import ROOT, Settings
from .geometry import fit_homography
from .models import Camera, Zone
from .store import Store

PLAN_W, PLAN_H = 1600, 1000
# BGR colours of the identity palette
PAPER, FINE = (234, 239, 237), (226, 231, 229)
INK, INK2, LINE = (42, 38, 34), (88, 82, 74), (186, 182, 174)
ORANGE, HI = (31, 91, 255), (74, 245, 228)

XS = [300, 460, 620, 780, 940, 1100]
YS = [200, 350, 500, 650]
EAST_EDGE = [(1040, 200), (1100, 200), (1100, 650), (1040, 650)]
POUR = [(460, 200), (780, 200), (780, 350), (460, 350)]
EXCAVATION = [(1180, 640), (1460, 620), (1480, 880), (1200, 900)]
CRANE_C, CRANE_R = (1300, 330), 180
LAYDOWN = [(120, 720), (560, 720), (560, 900), (120, 900)]

# plan point → image point (Sprint 0 zone corners in each clip's analysis frame)
CAM1_PAIRS = [((1100, 200), (748.8, 266.4)), ((1100, 650), (1273.6, 266.4)),
              ((1040, 650), (1273.6, 338.4)), ((1040, 200), (748.8, 338.4))]
CAM2_PAIRS = [((460, 200), (288.0, 768.0)), ((780, 200), (698.4, 704.0)),
              ((780, 350), (712.8, 1267.2)), ((460, 350), (302.4, 1267.2))]


def _dashed(img: np.ndarray, p1, p2, color, thick: int = 2, dash: int = 16, gap: int = 9) -> None:  # noqa: ANN001
    x1, y1 = p1
    x2, y2 = p2
    length = math.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return
    dx, dy = (x2 - x1) / length, (y2 - y1) / length
    pos = 0.0
    while pos < length:
        end = min(pos + dash, length)
        cv2.line(img, (int(x1 + dx * pos), int(y1 + dy * pos)), (int(x1 + dx * end), int(y1 + dy * end)),
                 color, thick, cv2.LINE_AA)
        pos += dash + gap


def _dashdot(img: np.ndarray, p1, p2, color) -> None:  # noqa: ANN001
    x1, y1 = p1
    x2, y2 = p2
    length = math.hypot(x2 - x1, y2 - y1)
    dx, dy = (x2 - x1) / length, (y2 - y1) / length
    pos, pattern, i = 0.0, (22, 6, 3, 6), 0
    while pos < length:
        seg = pattern[i % 4]
        if i % 2 == 0:
            end = min(pos + seg, length)
            cv2.line(img, (int(x1 + dx * pos), int(y1 + dy * pos)), (int(x1 + dx * end), int(y1 + dy * end)),
                     color, 1, cv2.LINE_AA)
        pos += seg
        i += 1


def _centered_text(img: np.ndarray, text: str, center, scale: float, color, thick: int = 2) -> None:  # noqa: ANN001
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
    cv2.putText(img, text, (int(center[0] - tw / 2), int(center[1] + th / 2)), cv2.FONT_HERSHEY_SIMPLEX,
                scale, color, thick, cv2.LINE_AA)


def _hatch(img: np.ndarray, polygon, color, spacing: int = 12) -> None:  # noqa: ANN001
    mask = np.zeros(img.shape[:2], np.uint8)
    cv2.fillPoly(mask, [np.array(polygon, np.int32)], 255)
    layer = img.copy()
    for c in range(-PLAN_H, PLAN_W + PLAN_H, spacing):
        cv2.line(layer, (c, 0), (c + PLAN_H, PLAN_H), color, 2, cv2.LINE_AA)
    img[mask > 0] = layer[mask > 0]


def draw_plan(path: Path) -> None:
    img = np.full((PLAN_H, PLAN_W, 3), PAPER, np.uint8)
    for x in range(0, PLAN_W, 40):
        cv2.line(img, (x, 0), (x, PLAN_H), FINE, 1)
    for y in range(0, PLAN_H, 40):
        cv2.line(img, (0, y), (PLAN_W, y), FINE, 1)
    for a, b in (((60, 60), (1540, 60)), ((1540, 60), (1540, 940)), ((1540, 940), (60, 940)), ((60, 940), (60, 60))):
        _dashed(img, a, b, INK2, 2)
    # site gate on the south boundary (opening + leaf swing)
    cv2.line(img, (640, 940), (760, 940), PAPER, 5)
    cv2.line(img, (640, 940), (640, 820), INK2, 2, cv2.LINE_AA)
    cv2.ellipse(img, (640, 940), (120, 120), 0, 270, 360, INK2, 1, cv2.LINE_AA)
    # structural grid
    for x in XS:
        _dashdot(img, (x, 140), (x, 700), LINE)
    for y in YS:
        _dashdot(img, (270, y), (1130, y), LINE)
    # slab
    slab = img.copy()
    cv2.rectangle(slab, (300, 200), (1100, 650), (226, 230, 228), -1)
    cv2.addWeighted(slab, 0.7, img, 0.3, 0, dst=img)
    for x in range(476, 780, 16):  # rebar mat in the pour bay
        cv2.line(img, (x, 204), (x, 346), (205, 205, 200), 1)
    for y in range(216, 350, 16):
        cv2.line(img, (464, y), (776, y), (205, 205, 200), 1)
    cv2.rectangle(img, (300, 200), (1100, 650), INK, 4, cv2.LINE_AA)
    for x in XS:
        for y in YS:
            cv2.rectangle(img, (x - 8, y - 8), (x + 8, y + 8), INK, -1)
    cv2.rectangle(img, (330, 230), (420, 310), INK, 2)
    cv2.line(img, (330, 230), (420, 310), INK, 1, cv2.LINE_AA)
    cv2.line(img, (420, 230), (330, 310), INK, 1, cv2.LINE_AA)
    # tower crane: swing radius, mast, jib
    for k in range(0, 360, 6):
        a0, a1 = math.radians(k), math.radians(k + 3.5)
        p0 = (int(CRANE_C[0] + CRANE_R * math.cos(a0)), int(CRANE_C[1] + CRANE_R * math.sin(a0)))
        p1 = (int(CRANE_C[0] + CRANE_R * math.cos(a1)), int(CRANE_C[1] + CRANE_R * math.sin(a1)))
        cv2.line(img, p0, p1, INK2, 2, cv2.LINE_AA)
    cv2.rectangle(img, (CRANE_C[0] - 13, CRANE_C[1] - 13), (CRANE_C[0] + 13, CRANE_C[1] + 13), INK, 2)
    cv2.line(img, (CRANE_C[0] - 13, CRANE_C[1] - 13), (CRANE_C[0] + 13, CRANE_C[1] + 13), INK, 1, cv2.LINE_AA)
    cv2.line(img, (CRANE_C[0] + 13, CRANE_C[1] - 13), (CRANE_C[0] - 13, CRANE_C[1] + 13), INK, 1, cv2.LINE_AA)
    jib_end = (int(CRANE_C[0] + CRANE_R * math.cos(math.radians(-35))), int(CRANE_C[1] + CRANE_R * math.sin(math.radians(-35))))
    cv2.line(img, CRANE_C, jib_end, INK, 3, cv2.LINE_AA)
    # excavation (hatched) and laydown yard
    _hatch(img, EXCAVATION, ORANGE)
    cv2.polylines(img, [np.array(EXCAVATION, np.int32)], True, ORANGE, 3, cv2.LINE_AA)
    for a, b in zip(LAYDOWN, LAYDOWN[1:] + LAYDOWN[:1]):
        _dashed(img, a, b, INK2, 2)
    for i, (x, y) in enumerate([(150, 750), (250, 750), (350, 750), (150, 820), (260, 830), (400, 800)]):
        cv2.rectangle(img, (x, y), (x + 70 + 10 * (i % 2), y + 40), INK2, 1)
    # grid bubbles
    for x, label in zip(XS, "ABCDEF"):
        cv2.circle(img, (x, 112), 18, PAPER, -1)
        cv2.circle(img, (x, 112), 18, INK, 2, cv2.LINE_AA)
        _centered_text(img, label, (x, 112), 0.7, INK)
    for y, label in zip(YS, "1234"):
        cv2.circle(img, (238, y), 18, PAPER, -1)
        cv2.circle(img, (238, y), 18, INK, 2, cv2.LINE_AA)
        _centered_text(img, label, (238, y), 0.7, INK)
    # north arrow
    c = (1490, 100)
    cv2.circle(img, c, 28, INK, 2, cv2.LINE_AA)
    cv2.fillPoly(img, [np.array([(c[0], c[1] - 22), (c[0] + 11, c[1] + 12), (c[0], c[1] + 5), (c[0] - 11, c[1] + 12)], np.int32)], INK)
    _centered_text(img, "N", (c[0], c[1] + 50), 0.7, INK)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)


def transcode_if_needed(src: Path, max_side: int, out_dir: Path) -> Path:
    """Downscale a large demo clip once (decoding 4K every loop wastes CPU)."""
    cap = cv2.VideoCapture(str(src))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    if max(w, h) <= max_side * 1.05:
        cap.release()
        return src
    scale = max_side / max(w, h)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    dst = out_dir / f"{src.stem}_{min(nw, nh)}p.mp4"
    if dst.exists():
        cap.release()
        return dst
    out_dir.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*"mp4v"), fps, (nw, nh))
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        writer.write(cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA))
    writer.release()
    cap.release()
    return dst


def _circle(center: tuple[int, int], r: int, n: int = 32) -> list[tuple[float, float]]:
    return [(round(center[0] + r * math.cos(2 * math.pi * i / n), 1), round(center[1] + r * math.sin(2 * math.pi * i / n), 1))
            for i in range(n)]


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def seed(store: Store, settings: Settings, reset: bool = False) -> dict:
    if reset:
        SQLModel.metadata.drop_all(store.engine)
        SQLModel.metadata.create_all(store.engine)
    elif store.list_cameras() or store.list_zones():
        return {"seeded": False, "reason": "site already has cameras or zones (use --reset to start over)"}

    draw_plan(settings.site_dir / "plan.png")
    store.update_site(name="موقع تجريبي – الرياض", plan_file="plan.png", plan_width=PLAN_W, plan_height=PLAN_H,
                      lat=24.7136, lon=46.6753)
    zones = [
        Zone(name="الحافة الشرقية للبلاطة", kind="no_entry", points=[list(p) for p in EAST_EDGE], outdoor=True),
        Zone(name="منطقة صبّ الخرسانة", kind="no_entry", points=[list(p) for p in POUR], outdoor=True),
        Zone(name="الحفريات المفتوحة", kind="no_entry", points=[list(p) for p in EXCAVATION], outdoor=True),
        Zone(name="نطاق الرافعة البرجية", kind="no_entry", points=[list(p) for p in _circle(CRANE_C, CRANE_R)],
             active=False, interlock=True, outdoor=True),
        Zone(name="ساحة التشوين", kind="ppe", points=[list(p) for p in LAYDOWN], require_helmet=True,
             require_vest=True, outdoor=True),
    ]
    for z in zones:
        store.save_zone(z)

    videos = ROOT / "data" / "videos"
    made, missing = [], []
    plan = [
        ("الحافة الشرقية للبلاطة", videos / "pexels_11798561.mp4", CAM1_PAIRS),
        ("منطقة صبّ الخرسانة", videos / "pexels_35631533.mp4", CAM2_PAIRS),
        ("مدخل الموقع", videos / "pexels_5434223.mp4", None),
    ]
    for name, path, pairs in plan:
        if not path.exists():
            missing.append(str(path))
            continue
        src = transcode_if_needed(path, settings.max_side, videos / "derived")
        cam = Camera(name=name, source=_rel(src))
        if pairs:
            H, err = fit_homography([p for p, _ in pairs], [i for _, i in pairs])
            cam.homography, cam.calib_error_px = H.tolist(), round(err, 3)
            cam.calib_pairs = [{"plan": list(p), "image": list(i)} for p, i in pairs]
        made.append(store.save_camera(cam).name)
    return {"seeded": True, "plan": str(settings.site_dir / "plan.png"), "zones": len(zones),
            "cameras": made, "missing_videos": missing}
