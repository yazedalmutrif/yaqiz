"""Shared definitions for the PPE v2 data workstream (see docs/DATA.md).

One registry (SOURCES) holds every dataset we use or evaluate on: where it comes from,
its licence and attribution, how to verify the download, how its classes map to the
unified class list, and which unified classes it labels *completely*.

The `labelled` set drives the label-mismatch handling: a class that a source does not
label is never treated as "background" for that source. It is filled with pseudo-labels
(scripts/data_pseudolabel.py) and never scored on that source's test split.
"""
from __future__ import annotations

import hashlib
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import DATASETS_DIR, MODELS_DIR, RUNS_DIR  # noqa: E402

# ---- Classes -------------------------------------------------------------------
# Target order from docs/SPEC.md §6 is helmet, head, vest, harness, machinery.
# No permissively licensed, no-login harness dataset was found (docs/DATA.md), so v2
# ships WITHOUT a harness class: an untrained "harness" output would switch on the
# backend's harness rule (yaqiz/rules.py checks model capabilities by class *name*)
# and raise false "harness missing" alerts. Consumers must map classes by name.
TARGET_CLASSES = ("helmet", "head", "vest", "harness", "machinery")
CLASSES = ("helmet", "head", "vest", "machinery")
CLS_ID = {n: i for i, n in enumerate(CLASSES)}

# ---- Paths ---------------------------------------------------------------------
DOWNLOADS_DIR = DATASETS_DIR / "_downloads"
V2_DIR = DATASETS_DIR / "ppe_v2"
SOURCES_DIR = V2_DIR / "sources"      # original labels only (teachers + all test splits)
MERGED_DIR = V2_DIR / "merged"        # original + pseudo labels (train/val of the final model)
PSEUDO_DIR = V2_DIR / "pseudo"        # pseudo-label records (jsonl) + spot-check sheets
FALLS_DIR = DATASETS_DIR.parent / "eval" / "falls"
V2_RUN_DIR = RUNS_DIR / "ppe_v2"
V1_WEIGHTS = MODELS_DIR / "ppe_yolo11s_best.pt"
V2_WEIGHTS = MODELS_DIR / "ppe_v2.pt"
SPLITS = ("train", "val", "test")
IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp")


@dataclass(frozen=True)
class Download:
    url: str | None            # None: no automated download possible (see `manual`)
    filename: str
    md5: str | None = None
    sha256: str | None = None
    size: int | None = None
    manual: str = ""           # what a human has to do when url is None or blocked


@dataclass(frozen=True)
class Source:
    name: str
    title: str
    licence: str
    licence_url: str
    attribution: str
    primary_page: str
    download: Download
    fmt: str                               # "voc" | "coco" | "yolo"
    class_map: dict[str, str | None]       # raw class name -> unified class (None = dropped)
    labelled: frozenset[str]               # unified classes this source labels completely
    split_note: str
    train_ok: bool = True                  # False: evaluation only (licence)
    notes: tuple[str, ...] = field(default_factory=tuple)
    # False: the source's own split (e.g. by recording date) is its leakage control, so near-duplicate
    # pairs WITHIN the source are not linked (fixed CCTV views make every frame of a camera look alike).
    dedupe_within: bool = True


SOURCES: dict[str, Source] = {
    "hardhat_xie": Source(
        name="hardhat_xie",
        title="Hardhat (a.k.a. 'Hard Hat Workers'), Xie Liangbin, Northeastern University (China)",
        licence="CC0 1.0",
        licence_url="https://creativecommons.org/publicdomain/zero/1.0/",
        attribution="Xie, Liangbin (2019). Hardhat. Harvard Dataverse, V1. https://doi.org/10.7910/DVN/7CBGOS",
        primary_page="https://doi.org/10.7910/DVN/7CBGOS",
        download=Download(
            url="https://dataverse.harvard.edu/api/access/datafile/3344658",
            filename="Hardhat.rar", md5="740824992600bb8983c7cc08516742ef",
            sha256="bb33a807de3c1523cc6095189a5c3355c803a54f09acf901fa3eca61dbd78241", size=268420501),
        fmt="voc",
        class_map={"helmet": "helmet", "head": "head", "person": None, "others": None},
        labelled=frozenset({"helmet", "head"}),
        split_note="official Train -> train/val (10% val, seed 0); official Test -> test",
        notes=("Roboflow's 'Hard Hat Workers' (CC0, 7,041 images) is a re-export of this dataset.",
               "'person' boxes are sparse (616 in 7,063 images), so persons are dropped."),
    ),
    "gdut_hwd": Source(
        name="gdut_hwd",
        title="GDUT-HWD (GDUT Hardhat Wearing Detection), Wu et al. 2019",
        licence="Apache-2.0 (LICENSE file of the GitHub repository that publishes the data)",
        licence_url="https://github.com/wujixiu/helmet-detection/blob/master/LICENSE",
        attribution=("Wu J., Cai N., Chen W., Wang H., Wang G. (2019). Automatic detection of hardhats worn by "
                     "construction personnel: A deep learning approach and benchmark dataset. Automation in "
                     "Construction 106, 102894. https://doi.org/10.1016/j.autcon.2019.102894"),
        primary_page="https://github.com/wujixiu/helmet-detection",
        download=Download(
            url="https://drive.usercontent.google.com/download?id=1CLHnPfBVwwxmlUmz83pG0SZjc7k_A7Qw&export=download&confirm=t",
            filename="GDUT-HWD.zip", md5="db717edef4f2cf2e4670b3bfde89b003",
            sha256="7eebc70964e7139384fcd80b7d7201e44d6741b99be4d72d8bed2dd77b637b67", size=678054820),
        fmt="voc",
        class_map={"blue": "helmet", "white": "helmet", "yellow": "helmet", "red": "helmet", "none": "head"},
        labelled=frozenset({"helmet", "head"}),
        split_note=("official trainval -> train/val (10% val, seed 0); 500 images sampled (seed 0) from the "
                    "official test list -> test; the other official-test images -> train"),
        notes=("The repository LICENSE (Apache-2.0) is the only licence statement; the data is linked from "
               "the README (Google Drive folder 12WtXQyM-7jWvWPtCXZlnycsIK72ClHgu).",),
    ),
    "chvg": Source(
        name="chvg",
        title="CHVG (Color Hardhat, Vest, Glass), Ferdous & Ahsan 2022",
        licence="CC BY 4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        attribution=("Ferdous M., Ahsan S.M.M. (2022). PPE detector: a YOLO-based architecture to detect personal "
                     "protective equipment (PPE) for construction sites. PeerJ Computer Science 8:e999. "
                     "https://doi.org/10.7717/peerj-cs.999 . Data: https://doi.org/10.6084/m9.figshare.19625166.v1"),
        primary_page="https://doi.org/10.6084/m9.figshare.19625166.v1",
        download=Download(
            url="https://ndownloader.figshare.com/files/34858290",
            filename="CHVG-Dataset.zip", md5="0239c0b26cf7f25dff4237e7a535a9a2",
            sha256="bb3d20d7f9bdcfff221d49a4cdbc4aa9a5a1617160e98a27ece0859b78744610", size=103985788),
        fmt="voc",
        class_map={"white": "helmet", "yellow": "helmet", "blue": "helmet", "red": "helmet",
                   "head": "head", "vest": "vest", "person": None, "glass": None},
        labelled=frozenset({"helmet", "head", "vest"}),
        split_note="no split in the release: seeded random split 75/10/15 (seed 0)",
        notes=("'head' = head without a hardhat (paper).",),
    ),
    "rf100_construction_safety": Source(
        name="rf100_construction_safety",
        title="construction-safety-gsnvb (Roboflow 100 benchmark)",
        licence="CC BY 4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        attribution=("'construction safety' dataset, Roboflow Universe (roboflow-100/construction-safety-gsnvb, "
                     "originally computer-vision/worker-safety), part of Roboflow 100: Ciaglia F. et al. (2022) "
                     "Roboflow 100: A Rich, Multi-Domain Object Detection Benchmark. arXiv:2211.13523"),
        primary_page="https://universe.roboflow.com/object-detection/construction-safety-gsnvb",
        download=Download(
            url="https://huggingface.co/datasets/Francesco/construction-safety-gsnvb/resolve/cd92c83884cc7c0ba1a3fda584784f550321e16f/dataset.tar.gz",
            filename="rf100_construction-safety-gsnvb.tar.gz",
            sha256="70e7b0c3f597f8e6b45e41fb22259de96feba8d763a93305a273384b13842763", size=75194830),
        fmt="coco",
        class_map={"helmet": "helmet", "no-helmet": "head", "vest": "vest", "person": None, "no-vest": None,
                   "construction-safety": None},
        labelled=frozenset({"helmet", "head", "vest"}),
        split_note="official train/valid/test",
        notes=("Images are stretched to 640x640 by Roboflow.",
               "Licence read from the Roboflow-generated README.dataset.txt inside the export "
               "('License: CC BY 4.0'); the Roboflow page itself refuses automated requests (HTTP 403)."),
    ),
    "rf100_excavators": Source(
        name="rf100_excavators",
        title="excavators-czvg9 (Roboflow 100 benchmark), originally 'Excavators' by Mohamed Sabek",
        licence="CC BY 4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        attribution=("'Excavators' dataset by Mohamed Sabek, Roboflow Universe (mohamed-sabek-6zmr6/excavators-cwlh0), "
                     "released in Roboflow 100 as excavators-czvg9: Ciaglia F. et al. (2022) arXiv:2211.13523"),
        primary_page="https://universe.roboflow.com/object-detection/excavators-czvg9",
        download=Download(
            url="https://huggingface.co/datasets/Francesco/excavators-czvg9/resolve/1b7367b5b3e359d23ace87d8f89053e7e6ee43fa/dataset.tar.gz",
            filename="rf100_excavators-czvg9.tar.gz",
            sha256="f7bc29b64d6bf086d0bd9f33169d58953f654d9f0040c2e97dd7fff6491b6351", size=192367757),
        fmt="coco",
        class_map={"EXCAVATORS": "machinery", "dump truck": "machinery", "wheel loader": "machinery",
                   "excavators": None},
        labelled=frozenset({"machinery"}),
        split_note=("official splits, except that every frame cut from the 5 source videos ('*_mp4-<n>') goes "
                    "to train, so no video spans train and val/test"),
        notes=("Machinery here = excavator, dump truck, wheel loader only (no cranes, dozers, mixers).",
               "Licence read from the Roboflow-generated README.dataset.txt inside the export."),
    ),
    "kr_site_machinery": Source(
        name="kr_site_machinery",
        title=("Development of an AI Dataset for Object Detection at Construction Sites (Na, Shin, Yun, Lee), "
               "Mendeley Data V2: the frames stored in the published archive's last part"),
        licence="CC BY 4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        attribution=("Na J., Shin H., Yun I., Lee J. (2025). Development of an AI Dataset for Object Detection at "
                     "Construction Sites. Mendeley Data, V2. https://doi.org/10.17632/rz8723t6d7.2"),
        primary_page="https://doi.org/10.17632/rz8723t6d7.2",
        download=Download(
            url="https://data.mendeley.com/public-files/datasets/rz8723t6d7/files/3339180e-a181-4d48-937e-14a72f40a572/file_downloaded",
            filename="kr_machinery_Bbox_dataset_classified.zip",
            sha256="66f69e1c5f368480729c15e3ed20dc6bf4467ddbb52aeef17c2d7da7c49c5a21", size=9365648759),
        fmt="voc",
        class_map={"excavator": "machinery", "dumptruck": "machinery", "bull_dozer": "machinery",
                   "crawler_drill": "machinery", "crane": "machinery", "fork_lift_truck": "machinery", "car": None},
        labelled=frozenset({"machinery"}),
        split_note=("by recording date, so no day appears in two splits: 2021-08-30 (foggy) and 2021-09-10 (sunny) "
                    "-> test; 2021-08-26 (foggy) -> val; the other dates -> train. Only every "
                    "KR_FRAME_STRIDE-th frame of each clip is unpacked (consecutive video frames are near-identical)"),
        notes=("The single file Mendeley publishes is the LAST part (disk 3 of 3) of a split ZIP; parts 1-2 are not "
               "published, so only the 23,132 labelled frames stored in part 3 (8 recording dates, 2021-08-26 to "
               "2021-09-13) can be read. Read with a ZIP reader that accepts the split-archive header "
               "(data_download.read_split_last_part).",
               "Wide fixed-camera views of one housing-development site in South Korea, 1920x1080.",
               "'car' boxes are dropped: cars are not heavy machinery.",
               "Test frames come from held-out DAYS of the same fixed cameras: they measure robustness to other "
               "days, weather and machine positions, not to new sites."),
        dedupe_within=False,
    ),
    "cppe_test": Source(
        name="cppe_test",
        title="Ultralytics Construction-PPE, test split only (evaluation/comparison, NOT used for training)",
        licence="AGPL-3.0",
        licence_url="https://docs.ultralytics.com/datasets/detect/construction-ppe/",
        attribution="Dalvi M., Singh N., Bhingarde S., Chalke K. (2025). Construction-PPE v1.0.0. Ultralytics.",
        primary_page="https://docs.ultralytics.com/datasets/detect/construction-ppe/",
        download=Download(url=None, filename="construction-ppe.zip",
                          sha256="bef8dcb599aa4e9d9f5e602cb6fa7143d3c84d7f6a0ff40463d7f2a4c2632ccc",
                          manual="fetched by scripts/get_dataset.py (Sprint 0)"),
        fmt="yolo",
        class_map={"helmet": "helmet", "no_helmet": "head", "vest": "vest", "gloves": None, "boots": None,
                   "goggles": None, "none": None, "Person": None, "no_goggle": None, "no_gloves": None,
                   "no_boots": None},
        labelled=frozenset({"helmet", "head", "vest"}),
        split_note="official test split (141 images); used only to compare v1 and v2",
        train_ok=False,
        notes=("Kept out of training because its licence (AGPL-3.0) is not permissive.",),
    ),
}

TRAIN_SOURCES = tuple(n for n, s in SOURCES.items() if s.train_ok)

# Pseudo-label classes that are NOT used, with the evidence (docs/DATA.md, "Pseudo-labels").
PSEUDO_DROP_CLASSES = {
    "machinery": ("teacher_mach was trained only on photos that contain machines; on the PPE sources it put "
                  "frame-sized boxes on people and whole scenes (2,545 of 4,862 Hardhat train/val images; every box "
                  "on the 16-image review sheet runs/ppe_v2/review/check_machinery_pseudo_hardhat_xie.jpg was wrong)"),
}
# Gear pseudo-labels must sit on a person found by the COCO detector (same head / torso regions as the
# live system, yaqiz/vision/analysis.py): this removes "helmets" on yellow machine parts and similar errors.
PERSON_FILTER = {"weights": "yolo11s.pt", "conf": 0.25, "imgsz": 960}


def pseudo_path(source: str) -> Path:
    """The pseudo-label records used for training: the filtered file when it exists."""
    filtered = PSEUDO_DIR / f"{source}.filtered.jsonl"
    return filtered if filtered.exists() else PSEUDO_DIR / f"{source}.jsonl"


def pseudo_is_stale(source: str) -> bool:
    """True when the filtered records are older than the raw ones (labels re-run without `filter`)."""
    raw, filtered = PSEUDO_DIR / f"{source}.jsonl", PSEUDO_DIR / f"{source}.filtered.jsonl"
    return raw.exists() and filtered.exists() and filtered.stat().st_mtime < raw.stat().st_mtime
KR_FRAME_STRIDE = 5  # kr_site_machinery: keep frames whose in-clip index is a multiple of this
KR_SPLIT_BY_DATE = {"20210830": "test", "20210910": "test", "20210826": "val"}  # every other date -> train

# Datasets checked and NOT used (reasons recorded in docs/DATA.md).
FALLS = Download(
    url="https://zenodo.org/api/records/13354453/files/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos-v2.1.zip/content",
    filename="GMDCSA24-v2.1.zip", md5="3d36f2c5c1a666b99639e4e9fd843efb",
    sha256="d455f90f67060b9c8032701d0a91ff38536eaa5ec85582a7a12e68351af591d7", size=1107545615)


# ---- Helpers -------------------------------------------------------------------
def file_hash(path: Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def seeded_split(items: list[str], fractions: dict[str, float], seed: int = 0) -> dict[str, str]:
    """Deterministic split of `items` (sorted first) into named parts by fraction."""
    items = sorted(items)
    rng = random.Random(seed)
    rng.shuffle(items)
    out: dict[str, str] = {}
    names = list(fractions)
    n = len(items)
    start = 0
    for k, name in enumerate(names):
        end = n if k == len(names) - 1 else start + round(fractions[name] * n)
        for it in items[start:end]:
            out[it] = name
        start = end
    return out


def yolo_line(cls_id: int, x1: float, y1: float, x2: float, y2: float, w: int, h: int) -> str | None:
    """Pixel xyxy -> normalised YOLO line, clipped to the image; None if degenerate."""
    x1, x2 = max(0.0, min(x1, x2)), min(float(w), max(x1, x2))
    y1, y2 = max(0.0, min(y1, y2)), min(float(h), max(y1, y2))
    bw, bh = x2 - x1, y2 - y1
    if bw < 1.0 or bh < 1.0:
        return None
    return f"{cls_id} {(x1 + bw / 2) / w:.6f} {(y1 + bh / 2) / h:.6f} {bw / w:.6f} {bh / h:.6f}"


def read_yolo(path: Path) -> list[tuple[int, float, float, float, float]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) >= 5:
            rows.append((int(p[0]), float(p[1]), float(p[2]), float(p[3]), float(p[4])))
    return rows


def images_in(folder: Path) -> list[Path]:
    return sorted(p for p in folder.glob("*") if p.suffix.lower() in IMG_EXTS)


def label_for(img: Path) -> Path:
    """Ultralytics convention: .../images/<split>/x.jpg -> .../labels/<split>/x.txt"""
    parts = list(img.parts)
    i = len(parts) - 1 - parts[::-1].index("images")
    parts[i] = "labels"
    return Path(*parts).with_suffix(".txt")


def link_or_copy(src: Path, dst: Path) -> None:
    import os
    import shutil
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def write_yaml(path: Path, data: dict) -> None:
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
