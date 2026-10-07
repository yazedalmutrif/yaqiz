"""Associate PPE detections (helmet / no_helmet / vest) with tracked person boxes.

The person boxes come from a COCO-pretrained detector + ByteTrack; the PPE
boxes come from the fine-tuned Construction-PPE model. A PPE box belongs to
the person whose head region (helmet classes) or torso region (vest) contains
the PPE box centre; ties go to the nearest region centre.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

HEAD_CLASSES = {"helmet", "no_helmet"}
TORSO_CLASSES = {"vest"}

# Region of the person box, as fractions of its height, measured from the top.
HEAD_REGION = (0.0, 0.35)
TORSO_REGION = (0.15, 0.75)
X_MARGIN = 0.15  # widen the person box by this fraction of its width on each side


@dataclass
class Det:
    cls: str
    conf: float
    xyxy: tuple[float, float, float, float]

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.xyxy
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


@dataclass
class PersonPPE:
    helmet: float = 0.0       # best helmet confidence matched to this person
    no_helmet: float = 0.0    # best no_helmet confidence matched to this person
    vest: float = 0.0
    matched: list[Det] = field(default_factory=list)

    @property
    def helmet_state(self) -> str | None:
        """'helmet', 'no_helmet' or None (nothing seen at the head)."""
        if self.helmet == 0.0 and self.no_helmet == 0.0:
            return None
        return "helmet" if self.helmet >= self.no_helmet else "no_helmet"


def _region(box: Sequence[float], frac: tuple[float, float]) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    return (x1 - X_MARGIN * w, y1 + frac[0] * h, x2 + X_MARGIN * w, y1 + frac[1] * h)


def _inside(pt: tuple[float, float], r: tuple[float, float, float, float]) -> bool:
    return r[0] <= pt[0] <= r[2] and r[1] <= pt[1] <= r[3]


def associate(person_boxes: Sequence[Sequence[float]], ppe: Sequence[Det]) -> list[PersonPPE]:
    """Return one PersonPPE per person box (same order)."""
    out = [PersonPPE() for _ in person_boxes]
    for det in ppe:
        if det.cls in HEAD_CLASSES:
            frac = HEAD_REGION
        elif det.cls in TORSO_CLASSES:
            frac = TORSO_REGION
        else:
            continue
        c = det.center
        best_i, best_d = None, float("inf")
        for i, box in enumerate(person_boxes):
            r = _region(box, frac)
            if not _inside(c, r):
                continue
            rc = ((r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0)
            d = (c[0] - rc[0]) ** 2 + (c[1] - rc[1]) ** 2
            if d < best_d:
                best_i, best_d = i, d
        if best_i is None:
            continue
        p = out[best_i]
        p.matched.append(det)
        if det.cls == "helmet":
            p.helmet = max(p.helmet, det.conf)
        elif det.cls == "no_helmet":
            p.no_helmet = max(p.no_helmet, det.conf)
        elif det.cls == "vest":
            p.vest = max(p.vest, det.conf)
    return out
