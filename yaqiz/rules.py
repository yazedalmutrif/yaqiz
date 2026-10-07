"""Per-camera rule engine: per-frame observations → debounced, cooled-down event candidates.

Each tracked person carries:
  * zone hysteresis (enter after `enter_frames`, leave after `exit_frames`),
  * majority votes for helmet / vest / harness over the last frames,
  * hold timers for PPE, SOS and man down.
An event is *opened* once, *updated* when it escalates, and *closed* when the condition clears
or the person is lost. A closed event starts a cooldown for that (person, rule).
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from .config import RuntimeSettings
from .posture import HoldTimer, ManDownDetector, PoseFeatures, SosDetector

PPE_ITEMS = ("helmet", "vest", "harness")


@dataclass(frozen=True)
class ZoneRule:
    id: int
    name: str
    kind: str                     # "no_entry" | "ppe"
    active: bool = True
    outdoor: bool = False
    require_helmet: bool = False
    require_vest: bool = False
    require_harness: bool = False
    interlock: bool = False


@dataclass
class PersonObs:
    track_id: int
    box: tuple[float, float, float, float]
    foot_img: tuple[float, float]
    foot_plan: tuple[float, float] | None
    zone_ids: frozenset[int]
    helmet: str | None = None     # "yes" | "no" | None (unknown this frame)
    vest: str | None = None
    harness: str | None = None
    pose: PoseFeatures | None = None
    near_machine: bool | None = None  # None: the PPE model has no machinery class


@dataclass
class Candidate:
    action: str                   # "open" | "update" | "close"
    key: tuple
    kind: str
    severity: str
    track_id: int
    zone_id: int | None = None
    item: str | None = None
    detail: dict = field(default_factory=dict)
    foot_img: tuple[float, float] | None = None
    foot_plan: tuple[float, float] | None = None
    box: tuple[float, float, float, float] | None = None
    duration_s: float = 0.0


class Vote:
    """Majority vote over the last `n` yes/no observations (None = no observation)."""

    def __init__(self, n: int = 12, min_votes: int = 3) -> None:
        self.hist: deque[str] = deque(maxlen=n)
        self.min_votes = min_votes

    def add(self, v: str | None) -> None:
        if v in ("yes", "no"):
            self.hist.append(v)

    @property
    def state(self) -> str | None:
        yes = sum(1 for v in self.hist if v == "yes")
        no = len(self.hist) - yes
        if no >= self.min_votes and no > yes:
            return "no"
        if yes >= self.min_votes and yes >= no:
            return "yes"
        return None


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


@dataclass
class _Track:
    last_seen: float
    foot_img: tuple[float, float] = (0.0, 0.0)
    box: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    zone_in: dict[int, int] = field(default_factory=dict)
    zone_out: dict[int, int] = field(default_factory=dict)
    inside: set[int] = field(default_factory=set)
    votes: dict[str, Vote] = field(default_factory=lambda: {i: Vote() for i in PPE_ITEMS})
    ppe_timers: dict[str, HoldTimer] = field(default_factory=dict)
    sos: SosDetector | None = None
    man_down: ManDownDetector | None = None
    mach_in: int = 0                  # consecutive frames next to a machine
    mach_out: int = 0
    open: dict[tuple, list] = field(default_factory=dict)        # key -> [start_t, severity, zone_id, item]
    closed_at: dict[tuple, float] = field(default_factory=dict)  # key -> t (cooldown)


class RuleEngine:
    DEDUPE_FRAC = 0.5    # "the same spot" = within half the person's height in the image ...
    MIN_DEDUPE_PX = 20.0  # ... but at least this many pixels
    SAME_BOX_IOU = 0.6    # two tracks in the same frame are one person only if their boxes overlap this much

    def __init__(self, rt: RuntimeSettings, zones: list[ZoneRule]) -> None:
        self.tracks: dict[int, _Track] = {}
        self._visible: set[int] = set()  # track IDs in the frame being processed
        self.recent: deque[tuple[float, tuple, tuple[float, float]]] = deque(maxlen=256)  # closed events
        self.configure(rt, zones)

    def configure(self, rt: RuntimeSettings, zones: list[ZoneRule]) -> None:
        self.rt = rt
        self.zones = {z.id: z for z in zones}

    # ------------------------------------------------------------------ helpers
    def _cooldown_ok(self, tr: _Track, key: tuple, t: float) -> bool:
        last = tr.closed_at.get(key)
        return last is None or t - last >= self.rt.cooldown_s

    def _duplicate(self, track_id: int, key: tuple, p: PersonObs, t: float) -> bool:
        """Is this person already covered by an event under another track ID?

        Trackers re-number people hidden behind rebar or each other: a track that is NOT in this frame and
        has an open event at the same spot is this person's old ID. Two tracks that ARE both in this frame are
        two people (two workers side by side each get an event), unless their boxes overlap almost
        completely (one person detected twice). "The same spot" scales with the person's height."""
        radius = max(self.MIN_DEDUPE_PX, self.DEDUPE_FRAC * max(p.box[3] - p.box[1], 1.0))
        for tid, other in self.tracks.items():
            if tid == track_id or key not in other.open:
                continue
            if tid in self._visible:
                if _iou(other.box, p.box) >= self.SAME_BOX_IOU:
                    return True
            elif math.dist(other.foot_img, p.foot_img) <= radius:
                return True
        return any(k == key and t - tc < self.rt.cooldown_s and math.dist(f, p.foot_img) <= 2 * radius
                   for tc, k, f in self.recent)

    def _open(self, out: list[Candidate], tr: _Track, p: PersonObs, t: float, key: tuple, kind: str,
              severity: str, zone_id: int | None = None, item: str | None = None, detail: dict | None = None) -> None:
        if key in tr.open or not self._cooldown_ok(tr, key, t) or self._duplicate(p.track_id, key, p, t):
            return
        tr.open[key] = [t, severity, zone_id, item]
        out.append(Candidate("open", (p.track_id, *key), kind, severity, p.track_id, zone_id, item,
                             dict(detail or {}), p.foot_img, p.foot_plan, p.box))

    def _close(self, out: list[Candidate], tr: _Track, track_id: int, key: tuple, t: float, reason: str) -> None:
        start, severity, zone_id, item = tr.open.pop(key)
        tr.closed_at[key] = t
        self.recent.append((t, key, tr.foot_img))
        out.append(Candidate("close", (track_id, *key), key[0], severity, track_id, zone_id, item,
                             {"reason": reason}, tr.foot_img, None, None, round(t - start, 2)))

    def track_status(self, track_id: int) -> str:
        tr = self.tracks.get(track_id)
        if not tr or not tr.open:
            return "ok"
        return "critical" if any(v[1] == "critical" for v in tr.open.values()) else "warn"

    def ppe_state(self, track_id: int, item: str) -> str | None:
        tr = self.tracks.get(track_id)
        return tr.votes[item].state if tr else None

    def inside_zones(self, track_id: int) -> set[int]:
        tr = self.tracks.get(track_id)
        return set(tr.inside) if tr else set()

    # ------------------------------------------------------------------ main step
    def update(self, persons: list[PersonObs], t: float, midday_ban: bool = False,
               capabilities: frozenset[str] = frozenset()) -> list[Candidate]:
        rt, out = self.rt, []
        seen: set[int] = set()
        self._visible = {p.track_id for p in persons}
        for p in persons:
            tr = self.tracks.get(p.track_id)
            if tr is None:
                tr = self.tracks[p.track_id] = _Track(last_seen=t)
                tr.sos, tr.man_down = SosDetector(rt.sos_hold_s), ManDownDetector(rt.man_down_s)
            tr.last_seen, tr.foot_img, tr.box = t, p.foot_img, p.box
            seen.add(p.track_id)

            # zone hysteresis
            for zid in self.zones:
                if zid in p.zone_ids:
                    tr.zone_in[zid] = tr.zone_in.get(zid, 0) + 1
                    tr.zone_out[zid] = 0
                    if zid not in tr.inside and tr.zone_in[zid] >= rt.enter_frames:
                        tr.inside.add(zid)
                else:
                    tr.zone_out[zid] = tr.zone_out.get(zid, 0) + 1
                    tr.zone_in[zid] = 0
                    if zid in tr.inside and tr.zone_out[zid] >= rt.exit_frames:
                        tr.inside.discard(zid)
            tr.inside &= set(self.zones)

            for item in PPE_ITEMS:
                tr.votes[item].add(getattr(p, item))

            # 1) entering an active no-entry zone; escalate if it lasts
            for zid in sorted(tr.inside):
                z = self.zones[zid]
                if z.kind != "no_entry" or not z.active:
                    continue
                key = ("zone_intrusion", zid)
                if key not in tr.open:
                    self._open(out, tr, p, t, key, "zone_intrusion", "warning", zid,
                               detail={"zone_name": z.name, "interlock": z.interlock})
                else:
                    rec = tr.open[key]
                    if rec[1] == "warning" and t - rec[0] >= rt.escalate_s:
                        rec[1] = "critical"
                        out.append(Candidate("update", (p.track_id, *key), "zone_intrusion", "critical",
                                             p.track_id, zid, None, {"zone_name": z.name, "escalated": True},
                                             p.foot_img, p.foot_plan, p.box, round(t - rec[0], 2)))

            # 2) PPE requirements (site-wide, overridden/extended by the zones the person is in)
            required: dict[str, int | None] = {}
            if rt.site_require_helmet:
                required["helmet"] = None
            if rt.site_require_vest:
                required["vest"] = None
            for zid in sorted(tr.inside):
                z = self.zones[zid]
                for item, flag in (("helmet", z.require_helmet), ("vest", z.require_vest),
                                   ("harness", z.require_harness)):
                    if flag:
                        required[item] = zid
            if "harness" not in capabilities:
                required.pop("harness", None)
            for item in PPE_ITEMS:
                timer = tr.ppe_timers.setdefault(item, HoldTimer(rt.ppe_hold_s, 0.5))
                missing = timer.update(item in required and tr.votes[item].state == "no", t)
                key = ("ppe_missing", item)
                if missing and item in required:
                    zid = required[item]
                    self._open(out, tr, p, t, key, "ppe_missing", "warning", zid, item,
                               detail={"item": item, "zone_name": self.zones[zid].name if zid else None})
                elif key in tr.open and (item not in required or tr.votes[item].state == "yes"):
                    self._close(out, tr, p.track_id, key, t, "resolved")

            # 3) outdoor work during the midday ban
            for zid in sorted(self.zones):
                z = self.zones[zid]
                key = ("midday_exposure", zid)
                if midday_ban and z.outdoor and zid in tr.inside:
                    self._open(out, tr, p, t, key, "midday_exposure", "warning", zid, detail={"zone_name": z.name})
                elif key in tr.open:
                    self._close(out, tr, p.track_id, key, t, "resolved")

            # 4) posture: SOS and man down
            if p.pose is not None:
                for kind, flag in (("sos", tr.sos.update(p.pose, t)), ("man_down", tr.man_down.update(p.pose, t))):
                    key = (kind,)
                    if flag:
                        zid = min(tr.inside) if tr.inside else None
                        self._open(out, tr, p, t, key, kind, "critical", zid,
                                   detail={"zone_name": self.zones[zid].name if zid else None})
                    elif key in tr.open:
                        self._close(out, tr, p.track_id, key, t, "resolved")

            # 5) next to machinery (struck-by / caught-between), debounced like a zone
            key = ("machine_proximity",)
            if p.near_machine is None:
                tr.mach_in = tr.mach_out = 0
                if key in tr.open:
                    self._close(out, tr, p.track_id, key, t, "resolved")
            else:
                tr.mach_in, tr.mach_out = (tr.mach_in + 1, 0) if p.near_machine else (0, tr.mach_out + 1)
                if tr.mach_in >= rt.enter_frames:
                    zid = min(tr.inside) if tr.inside else None
                    self._open(out, tr, p, t, key, "machine_proximity", "warning", zid,
                               detail={"zone_name": self.zones[zid].name if zid else None})
                elif key in tr.open and tr.mach_out >= rt.exit_frames:
                    self._close(out, tr, p.track_id, key, t, "moved_away")

            # close intrusions that no longer apply (left the zone, zone switched off or deleted)
            for key in [k for k in tr.open if k[0] == "zone_intrusion"]:
                zid = key[1]
                z = self.zones.get(zid)
                if z is None or not z.active or zid not in tr.inside:
                    self._close(out, tr, p.track_id, key, t, "left_zone")

        # lost tracks: close their events and forget them
        for tid in [tid for tid, tr in self.tracks.items() if tid not in seen and t - tr.last_seen > self.rt.lost_s]:
            tr = self.tracks[tid]
            for key in list(tr.open):
                self._close(out, tr, tid, key, t, "lost")
            del self.tracks[tid]
        return out
