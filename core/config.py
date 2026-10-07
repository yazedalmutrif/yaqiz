"""Central configuration. The product name lives ONLY here (PROJECT_NAME).

Change PROJECT_NAME to rebrand every overlay, log line and output name.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---- Branding (single source of truth) -------------------------------------
PROJECT_NAME = "Yaqiz"  # working name (Arabic: يقظ, "vigilant")

# ---- Paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent

# Keep Ultralytics' settings file and font cache inside the repo instead of
# %APPDATA%\Ultralytics. Must run before `import ultralytics` (all scripts import
# this module first and import ultralytics inside main()).
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))
Path(os.environ["YOLO_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)  # Ultralytics needs the parent to exist
DATA_DIR = ROOT / "data"
DATASETS_DIR = DATA_DIR / "datasets"
VIDEOS_DIR = DATA_DIR / "videos"
MODELS_DIR = ROOT / "models"
RUNS_DIR = ROOT / "runs"
ZONES_DIR = ROOT / "configs" / "zones"
SCREENSHOTS_DIR = ROOT / "docs" / "screenshots"

# ---- Dataset -----------------------------------------------------------------
# Ultralytics Construction-PPE (AGPL-3.0). See DATASETS.md.
DATASET_NAME = "construction-ppe"
DATASET_URL = (
    "https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-ppe.zip"
)
DATASET_CLASSES = {
    0: "helmet",
    1: "gloves",
    2: "vest",
    3: "boots",
    4: "goggles",
    5: "none",
    6: "Person",
    7: "no_helmet",
    8: "no_goggle",
    9: "no_gloves",
    10: "no_boots",
}

# ---- Models ------------------------------------------------------------------
PPE_BASE_WEIGHTS = "yolo11s.pt"      # COCO-pretrained start point for fine-tuning
PERSON_WEIGHTS = "yolo11s.pt"        # COCO model used for person detection + tracking
PPE_WEIGHTS = MODELS_DIR / "ppe_yolo11s_best.pt"  # copied here after training
COCO_PERSON_CLASS = 0


def configure_ultralytics() -> None:
    """Call right after importing ultralytics: no telemetry, datasets stay inside this repo."""
    from ultralytics import settings

    settings.update({"sync": False, "datasets_dir": str(DATASETS_DIR)})
