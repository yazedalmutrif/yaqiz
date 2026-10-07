"""OpenCV drawing helpers for annotated frames (zones, people, PPE, header bar)."""
from __future__ import annotations

from typing import Iterable, Sequence

import cv2
import numpy as np

from .config import PROJECT_NAME

# BGR colours
RED = (40, 40, 230)
AMBER = (0, 165, 255)
GREEN = (80, 190, 60)
GREY = (170, 170, 170)
WHITE = (255, 255, 255)
DARK = (25, 25, 25)
PPE_COLOURS = {"helmet": (255, 200, 0), "no_helmet": (200, 0, 255), "vest": (0, 230, 230), "Person": (200, 200, 200)}

FONT = cv2.FONT_HERSHEY_SIMPLEX


def _scale(img: np.ndarray) -> float:
    """Text/line scale: 1.0 for a 1920-px long side (landscape or portrait)."""
    return max(0.5, max(img.shape[:2]) / 1920.0)


def draw_zone(img: np.ndarray, pts: Sequence[tuple[int, int]], active: bool) -> None:
    """Translucent red polygon with outline (label drawn separately by draw_zone_label)."""
    s = _scale(img)
    poly = np.array(pts, dtype=np.int32).reshape(-1, 1, 2)
    layer = img.copy()
    cv2.fillPoly(layer, [poly], RED)
    alpha = 0.28 if active else 0.16
    cv2.addWeighted(layer, alpha, img, 1 - alpha, 0, dst=img)
    cv2.polylines(img, [poly], True, RED, max(2, int(3 * s)), cv2.LINE_AA)


def draw_zone_label(img: np.ndarray, pts: Sequence[tuple[int, int]], name: str, taken: list | None = None) -> None:
    """Zone name chip: below the polygon if there is room above the legend bar, else above it."""
    s = _scale(img)
    x = min(p[0] for p in pts)
    y_top = min(p[1] for p in pts)
    y_bot = max(p[1] for p in pts)
    chip_h = int(40 * s)
    if y_bot + chip_h < img.shape[0] - int(90 * s):
        org = (x, y_bot + chip_h - int(4 * s))
    else:
        org = (x, max(y_top - int(8 * s), int(30 * s)))
    label(img, f"DANGER ZONE: {name}", org, RED, taken=taken)


def _overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def label(img: np.ndarray, text: str, org: tuple[int, int], bg: tuple[int, int, int], fg=WHITE,
          taken: list | None = None) -> int:
    """Draw a filled text chip with its bottom-left at org. Returns the chip height.

    If `taken` (a list of already-drawn chip rectangles) is given, the chip is moved
    up until it no longer overlaps any of them, and its rectangle is appended.
    """
    s = _scale(img)
    fs, th = 0.7 * s, max(1, int(2 * s))
    (tw, tht), base = cv2.getTextSize(text, FONT, fs, th)
    pad = int(6 * s)
    h = tht + 2 * pad + base
    x, y = int(org[0]), int(org[1])
    x = max(0, min(x, img.shape[1] - tw - 2 * pad))
    y = max(tht + 2 * pad, y)
    rect = (x, y - tht - 2 * pad, x + tw + 2 * pad, y + base - pad // 2)
    if taken is not None:
        for _ in range(8):
            hit = next((r for r in taken if _overlaps(rect, r)), None)
            if hit is None:
                break
            y = hit[1] - (base - pad // 2) - int(2 * s)
            if y - tht - 2 * pad < 0:
                break
            rect = (x, y - tht - 2 * pad, x + tw + 2 * pad, y + base - pad // 2)
        taken.append(rect)
    cv2.rectangle(img, rect[:2], rect[2:], bg, -1)
    cv2.putText(img, text, (x + pad, y - pad), FONT, fs, fg, th, cv2.LINE_AA)
    return h


def draw_person(
    img: np.ndarray,
    box: Sequence[float],
    track_id: int,
    in_zone: bool,
    helmet: str,
    has_vest: bool,
    taken: list | None = None,
    show_label: bool = True,
) -> None:
    s = _scale(img)
    x1, y1, x2, y2 = (int(v) for v in box)
    if in_zone:
        colour = RED
    elif helmet == "no_helmet":
        colour = AMBER
    elif helmet == "helmet":
        colour = GREEN
    else:
        colour = GREY
    cv2.rectangle(img, (x1, y1), (x2, y2), colour, max(2, int(3 * s)), cv2.LINE_AA)
    fx, fy = (x1 + x2) // 2, y2
    cv2.circle(img, (fx, fy), max(4, int(6 * s)), colour, -1, cv2.LINE_AA)
    cv2.circle(img, (fx, fy), max(4, int(6 * s)), WHITE, 1, cv2.LINE_AA)

    if not (show_label or in_zone or helmet == "no_helmet"):
        return  # small, compliant / unknown person: box only, no chip (keeps far crowds readable)
    chips: list[tuple[str, tuple[int, int, int]]] = []
    if in_zone:
        chips.append(("IN DANGER ZONE", RED))
    if helmet == "no_helmet":
        chips.append(("NO HELMET", AMBER))
    if not chips:
        if helmet == "helmet":
            text = "OK helmet+vest" if has_vest else "OK helmet"
        else:
            text = "vest, helmet ?" if has_vest else "PPE ?"
        chips.append((text, colour))
    y = y1 - int(4 * s)
    for i, (text, bg) in enumerate(chips):
        txt = f"#{track_id} {text}" if i == 0 else text
        h = label(img, txt, (x1, y), bg, taken=taken)
        y -= h + int(2 * s)


def draw_ppe_boxes(img: np.ndarray, dets: Iterable) -> None:
    s = _scale(img)
    for d in dets:
        c = PPE_COLOURS.get(d.cls)
        if c is None:
            continue
        x1, y1, x2, y2 = (int(v) for v in d.xyxy)
        cv2.rectangle(img, (x1, y1), (x2, y2), c, max(1, int(2 * s)), cv2.LINE_AA)


def draw_header(img: np.ndarray, left: str, right: str = "") -> None:
    """Top bar: '<PROJECT_NAME> | left' and right-aligned 'right' (moved to a 2nd row if it would overlap)."""
    s = _scale(img)
    W = img.shape[1]
    fs, th = 0.8 * s, max(1, int(2 * s))
    pad, row = int(12 * s), int(40 * s)
    left_text = f"{PROJECT_NAME}  |  {left}"
    (lw, _), _ = cv2.getTextSize(left_text, FONT, fs, th)
    (rw, _), _ = cv2.getTextSize(right, FONT, fs, th) if right else ((0, 0), 0)
    two_rows = bool(right) and lw + rw + 3 * pad > W
    h = row * (2 if two_rows else 1) + int(6 * s)
    layer = img.copy()
    cv2.rectangle(layer, (0, 0), (W, h), DARK, -1)
    cv2.addWeighted(layer, 0.75, img, 0.25, 0, dst=img)
    cv2.putText(img, left_text, (pad, int(30 * s)), FONT, fs, WHITE, th, cv2.LINE_AA)
    if right:
        y = int(30 * s) + (row if two_rows else 0)
        cv2.putText(img, right, (W - rw - pad, y), FONT, fs, WHITE, th, cv2.LINE_AA)


def draw_legend(img: np.ndarray, show_ppe: bool = False, note: str = "") -> None:
    """Bottom bar: colour legend (wraps onto extra rows if needed) plus an optional note line."""
    s = _scale(img)
    fs, th = 0.55 * s, max(1, int(1.5 * s))
    items = [("in zone", RED), ("no helmet", AMBER), ("helmet seen", GREEN), ("PPE unknown", GREY)]
    if show_ppe:
        items += [("helmet box", PPE_COLOURS["helmet"]), ("vest box", PPE_COLOURS["vest"])]
    W, H = img.shape[1], img.shape[0]
    margin, row_h, sw = int(12 * s), int(28 * s), int(14 * s)

    # Lay out legend items into rows that fit the frame width.
    rows: list[list[tuple[str, tuple[int, int, int], int]]] = [[]]
    x = margin
    for text, c in items:
        (tw, _), _ = cv2.getTextSize(text, FONT, fs, th)
        w_item = sw + int(6 * s) + tw + int(24 * s)
        if rows[-1] and x + w_item > W - margin:
            rows.append([])
            x = margin
        rows[-1].append((text, c, x))
        x += w_item
    n_rows = len(rows) + (1 if note else 0)
    bar = n_rows * row_h + int(8 * s)

    layer = img.copy()
    cv2.rectangle(layer, (0, H - bar), (W, H), DARK, -1)
    cv2.addWeighted(layer, 0.75, img, 0.25, 0, dst=img)
    y = H - bar + row_h
    for row in rows:
        for text, c, x in row:
            cv2.rectangle(img, (x, y - sw), (x + sw, y), c, -1)
            cv2.putText(img, text, (x + sw + int(6 * s), y - int(1 * s)), FONT, fs, WHITE, th, cv2.LINE_AA)
        y += row_h
    if note:
        cv2.putText(img, note, (margin, y - int(1 * s)), FONT, fs, (200, 200, 200), th, cv2.LINE_AA)
