"""Model wrappers.

* PoseTracker: one per camera (Ultralytics keeps ByteTrack state inside the model), people only,
  with COCO-17 keypoints and stable track IDs.
* PPEDetector: one shared instance behind a lock. Class names from any of our PPE models are
  mapped to the canonical set: helmet, head (no helmet), vest, harness, machinery.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import numpy as np

from ..config import ROOT, Settings

log = logging.getLogger("yaqiz.engine")

CANONICAL = {
    "helmet": "helmet", "hardhat": "helmet", "hard_hat": "helmet", "hard-hat": "helmet",
    "head": "head", "no_helmet": "head", "no-hardhat": "head", "no_hardhat": "head", "nohelmet": "head",
    "vest": "vest", "safety_vest": "vest", "safety vest": "vest", "safety-vest": "vest",
    "harness": "harness", "safety_harness": "harness", "safety harness": "harness",
    "machinery": "machinery", "machine": "machinery", "excavator": "machinery", "loader": "machinery",
    "dozer": "machinery", "bulldozer": "machinery", "crane": "machinery", "mobile_crane": "machinery",
    "tower_crane": "machinery", "truck": "machinery", "dump_truck": "machinery", "mixer_truck": "machinery",
}


@dataclass(frozen=True)
class Det:
    cls: str
    conf: float
    xyxy: tuple[float, float, float, float]

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.xyxy
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


@dataclass(frozen=True)
class PersonDet:
    track_id: int
    conf: float
    xyxy: tuple[float, float, float, float]
    kpts: np.ndarray  # (17, 3): x, y, confidence


def suppress_nested(dets: list[Det], cls: str, frac: float = 0.6) -> list[Det]:
    """Drop a `cls` box when at least `frac` of its area lies inside an equally or more confident `cls` box.

    The detector sometimes boxes a machine's bucket or cab as well as the whole machine; keeping one box
    per machine makes the overlay readable. A part box that is MORE confident than the whole-machine box
    is kept too. Dropping a part box can only remove a "near" that came from the part sticking out of the
    kept box. Identical boxes count as nested, so duplicates are merged."""
    order = sorted((i for i, d in enumerate(dets) if d.cls == cls), key=lambda i: -dets[i].conf)
    kept: list[int] = []
    for i in order:
        x1, y1, x2, y2 = dets[i].xyxy
        area = max((x2 - x1) * (y2 - y1), 1e-6)
        nested = False
        for k in kept:
            kx1, ky1, kx2, ky2 = dets[k].xyxy
            ix = max(0.0, min(x2, kx2) - max(x1, kx1))
            iy = max(0.0, min(y2, ky2) - max(y1, ky1))
            if ix * iy >= frac * area:
                nested = True
                break
        if not nested:
            kept.append(i)
    keep = set(kept)
    return [d for i, d in enumerate(dets) if d.cls != cls or i in keep]


def cuda_gpu_supported(torch) -> bool:  # noqa: ANN001
    """True when the installed PyTorch build has kernels that run on NVIDIA GPU 0.

    The CUDA 13 build that setup installs has no kernels for GPUs older than the GTX 16 / RTX 20 series.
    On those GPUs torch.cuda.is_available() is still True, but every model call fails.
    """
    try:
        major, minor = torch.cuda.get_device_capability(0)
        archs = torch.cuda.get_arch_list()
    except Exception:  # noqa: BLE001 - a GPU that cannot even be queried is not usable
        return False
    if not archs:
        return True                   # the build does not say; let PyTorch try
    cap = major * 10 + minor
    for arch in archs:                # e.g. "sm_86", "sm_90a", "sm_100f", "compute_90"
        kind, _, rest = arch.partition("_")
        num = rest.rstrip("abcdefghijklmnopqrstuvwxyz")
        suffix = rest[len(num):]
        if not num.isdigit():
            continue
        n = int(num)
        if suffix == "a":
            ok = n == cap                           # architecture-specific: this exact GPU only
        elif kind == "sm" or suffix == "f":
            ok = n // 10 == major and n <= cap      # machine code or family PTX: same major, same or newer minor
        else:
            ok = kind == "compute" and n <= cap     # plain PTX: the driver compiles it for any newer GPU
        if ok:
            return True
    return False


_warned_unsupported_gpu = False


def _warn_unsupported_gpu(torch) -> None:  # noqa: ANN001
    global _warned_unsupported_gpu
    if _warned_unsupported_gpu:
        return
    _warned_unsupported_gpu = True
    try:
        major, minor = torch.cuda.get_device_capability(0)
        gpu = f"{torch.cuda.get_device_name(0)}, compute capability {major}.{minor}"
    except Exception:  # noqa: BLE001
        gpu = "GPU 0"
    log.warning("this PyTorch build cannot run on the NVIDIA GPU (%s); using the CPU instead, which is slower", gpu)


def pick_device(settings: Settings):  # noqa: ANN201
    if settings.device:
        return settings.device
    import torch

    if torch.cuda.is_available():
        if cuda_gpu_supported(torch):
            return 0                  # NVIDIA GPU (Windows / Linux)
        _warn_unsupported_gpu(torch)  # e.g. a GTX 10-series GPU: fall back below
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"                  # Apple GPU (Mac with Apple Silicon)
    return "cpu"


class PPEDetector:
    def __init__(self, settings: Settings) -> None:
        from ultralytics import YOLO

        self.path = settings.resolve_ppe_weights()
        self.model = YOLO(str(self.path))
        self.device = pick_device(settings)
        self.imgsz = settings.imgsz
        self.lock = threading.Lock()
        self.class_map = {int(i): CANONICAL.get(str(n).lower().strip()) for i, n in self.model.names.items()}
        self.capabilities = frozenset(v for v in self.class_map.values() if v)

    def detect(self, frame: np.ndarray, conf: float) -> list[Det]:
        with self.lock:
            res = self.model.predict(frame, imgsz=self.imgsz, conf=conf, device=self.device,
                                     verbose=False)[0]
        boxes = res.boxes
        if boxes is None or len(boxes) == 0:
            return []
        xyxy = boxes.xyxy.cpu().numpy()
        cls = boxes.cls.cpu().numpy().astype(int)
        cf = boxes.conf.cpu().numpy()
        out = []
        for b, c, p in zip(xyxy, cls, cf):
            name = self.class_map.get(int(c))
            if name:
                out.append(Det(name, float(p), (float(b[0]), float(b[1]), float(b[2]), float(b[3]))))
        return suppress_nested(out, "machinery")


class PersonTracker:
    """COCO detector + ByteTrack (one per camera: Ultralytics keeps tracker state in the model)."""

    def __init__(self, settings: Settings) -> None:
        from ultralytics import YOLO

        self.model = YOLO(str(settings.model_path(settings.person_weights)))
        self.device = pick_device(settings)
        self.imgsz = settings.imgsz
        site_cfg = ROOT / "configs" / "bytetrack_site.yaml"
        self.tracker_cfg = str(site_cfg) if site_cfg.exists() else "bytetrack.yaml"

    def track(self, frame: np.ndarray, conf: float) -> list[tuple[int, float, tuple[float, float, float, float]]]:
        res = self.model.track(frame, persist=True, tracker=self.tracker_cfg, classes=[0], conf=conf,
                               imgsz=self.imgsz, device=self.device, verbose=False)[0]
        boxes = res.boxes
        if boxes is None or boxes.id is None or len(boxes) == 0:
            return []
        ids = boxes.id.cpu().numpy().astype(int)
        xyxy = boxes.xyxy.cpu().numpy()
        cf = boxes.conf.cpu().numpy()
        return [(int(i), float(c), (float(b[0]), float(b[1]), float(b[2]), float(b[3]))) for i, c, b in zip(ids, cf, xyxy)]


class PoseEstimator:
    """YOLO11-pose for COCO-17 keypoints (no tracking; matched to tracked people by box overlap)."""

    def __init__(self, settings: Settings) -> None:
        from ultralytics import YOLO

        self.model = YOLO(str(settings.model_path(settings.pose_weights)))
        self.device = pick_device(settings)
        self.imgsz = settings.pose_imgsz

    def estimate(self, frame: np.ndarray, conf: float) -> list[tuple[tuple[float, float, float, float], np.ndarray]]:
        res = self.model.predict(frame, classes=[0], conf=conf, imgsz=self.imgsz, device=self.device, verbose=False)[0]
        boxes = res.boxes
        if boxes is None or len(boxes) == 0 or res.keypoints is None:
            return []
        xyxy = boxes.xyxy.cpu().numpy()
        kps = res.keypoints.data.cpu().numpy()
        if kps.shape[-1] == 2:
            kps = np.concatenate([kps, np.ones(kps.shape[:-1] + (1,))], axis=-1)
        return [((float(b[0]), float(b[1]), float(b[2]), float(b[3])), k) for b, k in zip(xyxy, kps)]


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


NO_KPTS = np.zeros((17, 3))


def attach_keypoints(tracks, poses, cache: dict, t: float, max_age: float = 0.6) -> list[PersonDet]:  # noqa: ANN001
    """Give each tracked person keypoints: from this frame's pose results (best IoU >= 0.3), else the
    track's last keypoints shifted with its box (if recent), else none (posture then uses the box)."""
    used: set[int] = set()
    out: list[PersonDet] = []
    for tid, conf, box in tracks:
        kpts = None
        if poses:
            best, best_iou = None, 0.3
            for j, (pbox, k) in enumerate(poses):
                if j not in used:
                    v = iou(box, pbox)
                    if v >= best_iou:
                        best, best_iou = j, v
            if best is not None:
                used.add(best)
                kpts = poses[best][1]
                cache[tid] = (kpts, box, t)
        if kpts is None and tid in cache and t - cache[tid][2] <= max_age:
            old_k, old_box, _ = cache[tid]
            dx = (box[0] + box[2] - old_box[0] - old_box[2]) / 2.0
            dy = (box[1] + box[3] - old_box[1] - old_box[3]) / 2.0
            kpts = old_k.copy()
            kpts[:, 0] += dx
            kpts[:, 1] += dy
        out.append(PersonDet(tid, conf, box, NO_KPTS if kpts is None else kpts))
    for tid in [k for k, v in cache.items() if t - v[2] > 5.0]:
        del cache[tid]
    return out
