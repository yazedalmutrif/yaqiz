"""Find near-duplicate images across all sources and splits, so no test image leaks into training.

Web-collected PPE datasets re-use each other's photos (CHVG says most of its images come from
earlier datasets), so the same picture can sit in one source's train split and another
source's test split. This script hashes every image (64-bit difference hash, plus the hash of
the mirrored image), links pairs within --threshold bits, and decides:

  * a group that contains any test image (any source, including the Construction-PPE test
    split used for the v1/v2 comparison): all its train/val members are excluded;
  * a group with only train/val members: one member is kept (train before val, then the source
    that labels the most classes), the rest are excluded.

A source with dedupe_within=False (fixed-camera video split by recording date) is only checked
against OTHER sources: its own date split is its leakage control.

Writes data/datasets/ppe_v2/dedupe.json; data_build.py and data_pseudolabel.py honour it.

Usage:  .venv\\Scripts\\python scripts\\data_dedupe.py [--threshold 5]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_common import SOURCES, SOURCES_DIR, SPLITS, TRAIN_SOURCES, V2_DIR, images_in  # noqa: E402


def dhash_pair(path: Path) -> tuple[int, int]:
    buf = np.fromfile(str(path), np.uint8)
    im = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    if im is None:
        raise RuntimeError(f"cannot read {path}")
    small = cv2.resize(im, (9, 8), interpolation=cv2.INTER_AREA).astype(np.int16)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    flipped = small[:, ::-1]
    fbits = (flipped[:, 1:] > flipped[:, :-1]).flatten()
    to_int = lambda b: int("".join("1" if x else "0" for x in b), 2)  # noqa: E731
    return to_int(bits), to_int(fbits)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=int, default=6, help="max Hamming distance (of 64 bits) for a duplicate")
    ap.add_argument("--out", default=str(V2_DIR / "dedupe.json"))
    ap.add_argument("--link-within-all", action="store_true",
                    help="ignore dedupe_within=False (shows what the exemption avoids; use with --out)")
    args = ap.parse_args()

    entries = []  # (source, split, filename, path)
    for name in SOURCES:
        for split in SPLITS:
            for p in images_in(SOURCES_DIR / name / "images" / split):
                entries.append((name, split, p.name, p))
    print(f"hashing {len(entries)} images ...")
    with ThreadPoolExecutor(max_workers=12) as ex:
        hashes = list(ex.map(lambda e: dhash_pair(e[3]), entries))
    h = np.array([a for a, _ in hashes], dtype=np.uint64)
    hf = np.array([b for _, b in hashes], dtype=np.uint64)

    parent = list(range(len(entries)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    pairs = []
    n = len(entries)
    for start in range(0, n, 1024):
        blk = h[start:start + 1024, None]
        d = np.minimum(np.bitwise_count(blk ^ h[None, :]), np.bitwise_count(blk ^ hf[None, :]))
        ii, jj = np.nonzero(d <= args.threshold)
        for i, j in zip(ii + start, jj):
            if j > i and (args.link_within_all
                          or not (entries[i][0] == entries[j][0] and not SOURCES[entries[i][0]].dedupe_within)):
                pairs.append((int(i), int(j), int(d[i - start, j])))
                parent[find(int(i))] = find(int(j))
    groups = collections.defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    groups = {r: m for r, m in groups.items() if len(m) > 1}

    member_lists = [[entries[i][:3] for i in m] for m in groups.values()]
    excluded, reasons, report = decide(member_lists, set(TRAIN_SOURCES))
    cross_source = sum(1 for m in groups.values() if len({entries[i][0] for i in m}) > 1)
    summary = {
        "method": "64-bit dHash of the grayscale image (and of its mirror), Hamming distance <= threshold",
        "threshold": args.threshold,
        "images_hashed": n,
        "duplicate_pairs": len(pairs),
        "duplicate_groups": len(groups),
        "groups_spanning_sources": cross_source,
        "excluded_counts": {f"{s}/{sp}": len(v) for s, d in excluded.items() for sp, v in d.items()},
        "excluded_by_reason": {f"{s}/{sp}: {r}": c for (s, sp, r), c in sorted(reasons.items())},
    }
    out = {"summary": summary, "excluded": {s: dict(d) for s, d in excluded.items()}, "groups": report}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


def decide(groups: list[list[tuple[str, str, str]]], train_sources: set[str]):
    """Apply the keep/drop rule to duplicate groups of (source, split, filename).

    Only train/val members of `train_sources` can be dropped or kept; test members of any
    source (including evaluation-only sources) count as test images."""
    richness = {k: len(s.labelled) for k, s in SOURCES.items()}
    excluded = collections.defaultdict(lambda: collections.defaultdict(list))
    reasons = collections.Counter()
    report = []
    for members in groups:
        has_test = any(sp == "test" for _, sp, _ in members)
        trainval = [m for m in members if m[1] != "test" and m[0] in train_sources]
        if not trainval:
            continue
        if has_test:
            drop, reason = trainval, "duplicates a test image"
        else:
            keep = sorted(trainval, key=lambda m: (m[1] != "train", -richness[m[0]], m[0], m[2]))[0]
            drop, reason = [m for m in trainval if m != keep], "duplicate within train/val"
        for s, sp, fn in drop:
            excluded[s][sp].append(fn)
            reasons[(s, sp, reason)] += 1
        report.append({"members": ["/".join(m) for m in members], "excluded": ["/".join(m) for m in drop],
                       "reason": reason})
    return excluded, reasons, report


def excluded_for(train_sources: set[str]) -> dict[str, dict[str, set[str]]]:
    """Exclusions for a training run that uses only `train_sources` (e.g. a teacher model)."""
    p = V2_DIR / "dedupe.json"
    if not p.exists():
        raise SystemExit("Run scripts/data_dedupe.py first.")
    groups = [[tuple(m.split("/", 2)) for m in g["members"]] for g in json.loads(p.read_text(encoding="utf-8"))["groups"]]
    excluded, _, _ = decide(groups, set(train_sources))
    return {s: {sp: set(v) for sp, v in d.items()} for s, d in excluded.items()}


if __name__ == "__main__":
    raise SystemExit(main())
