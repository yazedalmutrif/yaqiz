"""Build the merged PPE v2 training set and the held-out test sets.

Train/val (data/datasets/ppe_v2/merged/<source>/...): every train/val image of every
permissively licensed source, minus near-duplicates (data_dedupe.py), with its ORIGINAL labels
plus the pseudo-labels (data_pseudolabel.py) for the classes that source does not label.

Test (data/datasets/ppe_v2/sources/<source>/images/test): original labels only. One YAML per
source, one per class over the sources that label that class ("combined"), the Construction-PPE
test split in v2 classes (test_cppe_test.yaml), and copies of all of these in the Sprint-0 model's
class indices (v1space/) so v1 and v2 can be scored on exactly the same boxes.

Usage:  .venv\\Scripts\\python scripts\\data_build.py [--no-pseudo]
"""
from __future__ import annotations

import argparse
import collections
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_common import (  # noqa: E402
    CLASSES, CLS_ID, DATASETS_DIR, MERGED_DIR, PSEUDO_DIR, SOURCES, SOURCES_DIR, TRAIN_SOURCES, V2_DIR,
    images_in, label_for, link_or_copy, pseudo_is_stale, pseudo_path, write_yaml)
from data_dedupe import excluded_for  # noqa: E402

V1_NAMES = {0: "helmet", 1: "gloves", 2: "vest", 3: "boots", 4: "goggles", 5: "none", 6: "Person",
            7: "no_helmet", 8: "no_goggle", 9: "no_gloves", 10: "no_boots"}
V2_TO_V1 = {CLS_ID["helmet"]: 0, CLS_ID["head"]: 7, CLS_ID["vest"]: 2}  # machinery has no v1 class


def load_pseudo(src: str) -> dict[tuple[str, str], list[str]]:
    out = collections.defaultdict(list)
    p = pseudo_path(src)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            x1, y1, x2, y2 = r["xyxyn"]
            out[(r["split"], r["image"])].append(
                f"{CLS_ID[r['cls']]} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}")
    return out


def write_list(name: str, imgs: list[Path]) -> Path:
    p = V2_DIR / "lists" / f"{name}.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(i.as_posix() for i in imgs) + "\n", encoding="utf-8")
    return p


def test_yaml(name: str, imgs: list[Path], names: dict[int, str], subdir: str = "") -> Path:
    lst = write_list(f"test_{subdir + '_' if subdir else ''}{name}", imgs)
    y = V2_DIR / (f"{subdir}/" if subdir else "") / f"test_{name}.yaml"
    write_yaml(y, {"path": V2_DIR.as_posix(), "train": lst.as_posix(), "val": lst.as_posix(),
                   "test": lst.as_posix(), "names": names})
    return y


def v1_copy(src: str, imgs: list[Path]) -> list[Path]:
    """Hard-link test images into v1space/<src>/images/test and write labels in v1 class ids."""
    out = []
    for p in imgs:
        dst = V2_DIR / "v1space" / src / "images" / "test" / p.name
        link_or_copy(p, dst)
        lines = []
        for line in label_for(p).read_text(encoding="utf-8").splitlines():
            c, *rest = line.split()
            if int(c) in V2_TO_V1:
                lines.append(" ".join([str(V2_TO_V1[int(c)]), *rest]))
        lab = label_for(dst)
        lab.parent.mkdir(parents=True, exist_ok=True)
        lab.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        out.append(dst)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pseudo", action="store_true", help="ablation: merge without pseudo-labels")
    args = ap.parse_args()
    if not args.no_pseudo and not (PSEUDO_DIR / "summary.json").exists():
        raise SystemExit("Run scripts/data_pseudolabel.py label first (or pass --no-pseudo).")
    if not args.no_pseudo and not all((PSEUDO_DIR / f"{s}.filtered.jsonl").exists() for s in TRAIN_SOURCES):
        raise SystemExit("Run scripts/data_pseudolabel.py filter first (the build uses the filtered records).")
    stale = [s for s in TRAIN_SOURCES if pseudo_is_stale(s)]
    if not args.no_pseudo and stale:
        raise SystemExit(f"Filtered pseudo-labels are older than the labels for {stale}: run data_pseudolabel.py filter.")
    merged = MERGED_DIR if not args.no_pseudo else V2_DIR / "merged_nopseudo"
    if merged.exists():
        shutil.rmtree(merged)
    excluded = excluded_for(set(TRAIN_SOURCES))
    names = dict(enumerate(CLASSES))
    stats = {"train": {}, "val": {}}
    lists = {"train": [], "val": []}
    for src in TRAIN_SOURCES:
        pseudo = {} if args.no_pseudo else load_pseudo(src)
        for split in ("train", "val"):
            drop = excluded.get(src, {}).get(split, set())
            c_orig, c_pseudo = collections.Counter(), collections.Counter()
            n = 0
            for p in images_in(SOURCES_DIR / src / "images" / split):
                if p.name in drop:
                    continue
                dst = merged / src / "images" / split / p.name
                link_or_copy(p, dst)
                orig = label_for(p).read_text(encoding="utf-8").splitlines()
                extra = pseudo.get((split, p.name), [])
                for line in orig:
                    c_orig[CLASSES[int(line.split()[0])]] += 1
                for line in extra:
                    c_pseudo[CLASSES[int(line.split()[0])]] += 1
                lab = label_for(dst)
                lab.parent.mkdir(parents=True, exist_ok=True)
                body = orig + extra
                lab.write_text("\n".join(body) + ("\n" if body else ""), encoding="utf-8")
                lists[split].append(dst)
                n += 1
            stats[split][src] = {"images": n, "excluded_duplicates": len(drop),
                                 "original_boxes": dict(c_orig), "pseudo_boxes": dict(c_pseudo)}
    tag = "" if not args.no_pseudo else "_nopseudo"
    train_list = write_list(f"v2_train{tag}", lists["train"])
    val_list = write_list(f"v2_val{tag}", lists["val"])
    write_yaml(V2_DIR / f"ppe_v2{tag}.yaml", {"path": V2_DIR.as_posix(), "train": train_list.as_posix(),
                                              "val": val_list.as_posix(), "names": names})

    # ---- test sets (original labels only) ----
    tests = {}
    for src, s in SOURCES.items():
        imgs = images_in(SOURCES_DIR / src / "images" / "test")
        tests[src] = imgs
        test_yaml(src, imgs, names)
        test_yaml(src, v1_copy(src, imgs), V1_NAMES, subdir="v1space")
    for cls in CLASSES:
        srcs = [s for s in TRAIN_SOURCES if cls in SOURCES[s].labelled]
        imgs = [p for s in srcs for p in tests[s]]
        test_yaml(f"combined_{cls}", imgs, names)
        if CLS_ID[cls] in V2_TO_V1:
            test_yaml(f"combined_{cls}", [V2_DIR / "v1space" / s / "images" / "test" / p.name for s in srcs
                                          for p in tests[s]], V1_NAMES, subdir="v1space")
    summary = {
        "classes": names,
        "train_images": len(lists["train"]), "val_images": len(lists["val"]),
        "test_images": {s: len(v) for s, v in tests.items()},
        "per_source": stats,
        "totals": {split: {kind: dict(sum((collections.Counter(v[kind]) for v in stats[split].values()),
                                          collections.Counter()))
                           for kind in ("original_boxes", "pseudo_boxes")} for split in stats},
    }
    (V2_DIR / f"build_stats{tag}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    print(f"data yaml: {V2_DIR / f'ppe_v2{tag}.yaml'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
