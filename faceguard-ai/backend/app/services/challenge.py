"""Active-liveness challenge engine (Phase 6): a deterministic state machine over landmark measurements.

IMPORTANT: passing a blink/head-turn challenge shows that a face in view moved as asked. It does NOT prove a live
person: a replayed video, a deepfake or a puppeted photo can satisfy it. The outcome is therefore never REAL; a
passed challenge is reported as evidence next to an UNCERTAIN verdict unless a validated model also decides.
"""
from __future__ import annotations

import enum
import math
import random
from app.core.i18n import tr
from dataclasses import dataclass, field

# iBUG 68-point indices
RIGHT_EYE = (36, 37, 38, 39, 40, 41)
LEFT_EYE = (42, 43, 44, 45, 46, 47)
NOSE_TIP, JAW_LEFT, JAW_RIGHT = 30, 0, 16


class Kind(str, enum.Enum):
    BLINK = "BLINK"
    TURN_LEFT = "TURN_LEFT"
    TURN_RIGHT = "TURN_RIGHT"


class State(str, enum.Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


@dataclass(frozen=True)
class Config:
    sequence_length: int = 2
    allowed: tuple[Kind, ...] = (Kind.BLINK, Kind.TURN_LEFT, Kind.TURN_RIGHT)
    timeout_seconds: float = 8.0  # per challenge
    max_attempts: int = 2
    ear_closed: float = 0.19
    ear_open: float = 0.24
    min_closed_frames: int = 1
    turn_threshold: float = 0.30  # |yaw_ratio| needed, yaw_ratio in -1..1, 0 = frontal
    neutral_band: float = 0.15  # must start (and for blink, stay) within this band
    hold_frames: int = 2
    mirrored_display: bool = True  # preview is mirrored like a mirror, so "your left" = image right


def eye_aspect_ratio(pts: list[tuple[float, float]], idx: tuple[int, ...]) -> float:
    p = [pts[i] for i in idx]
    d = lambda a, b: math.dist(a, b)  # noqa: E731
    horizontal = d(p[0], p[3])
    return (d(p[1], p[5]) + d(p[2], p[4])) / (2 * horizontal) if horizontal > 0 else 0.0


def measure(landmarks: list[tuple[float, float]]) -> tuple[float, float]:
    """Returns (ear, yaw_ratio) from 68 landmarks. yaw_ratio: -1 = nose at image-left jaw edge, +1 = image-right."""
    if len(landmarks) != 68:
        raise ValueError("68 landmarks required")
    ear = (eye_aspect_ratio(landmarks, RIGHT_EYE) + eye_aspect_ratio(landmarks, LEFT_EYE)) / 2
    left, right = landmarks[JAW_LEFT][0], landmarks[JAW_RIGHT][0]
    width = right - left
    yaw = 0.0 if width <= 0 else ((landmarks[NOSE_TIP][0] - left) / width - 0.5) * 2
    return ear, yaw


@dataclass
class Observation:
    t: float  # seconds (monotonic)
    face_count: int
    ear: float | None = None
    yaw: float | None = None


@dataclass
class _Step:
    kind: Kind
    state: State = State.PENDING
    started_at: float | None = None
    saw_open: bool = False
    closed_frames: int = 0
    held: int = 0
    saw_neutral: bool = False
    reason: str | None = None


INSTRUCTIONS = {Kind.BLINK: "Blink once, naturally.", Kind.TURN_LEFT: "Slowly turn your head to your left.",
                Kind.TURN_RIGHT: "Slowly turn your head to your right."}


def make_sequence(cfg: Config, seed: int | None = None) -> list[Kind]:
    """Random order, never repeating the same kind twice in a row when more than one kind is allowed."""
    rng = random.Random(seed)
    seq: list[Kind] = []
    for _ in range(cfg.sequence_length):
        options = [k for k in cfg.allowed if not seq or k != seq[-1]] or list(cfg.allowed)
        seq.append(rng.choice(options))
    return seq


class ChallengeSession:
    def __init__(self, cfg: Config, sequence: list[Kind]):
        if not sequence:
            raise ValueError("empty challenge sequence")
        self.cfg, self.attempt = cfg, 1
        self._sequence = list(sequence)
        self._steps = [_Step(k) for k in sequence]
        self.index = 0
        self.finished = False
        self.outcome: str | None = None  # "PASSED" | "FAILED" | "TIMED_OUT" | "UNAVAILABLE"

    # -- public view -------------------------------------------------------------------------------
    @property
    def current(self) -> _Step | None:
        return None if self.finished else self._steps[self.index]

    def progress(self) -> dict:
        cur = self.current
        return {
            "attempt": self.attempt, "max_attempts": self.cfg.max_attempts, "index": self.index,
            "total": len(self._steps), "finished": self.finished, "outcome": self.outcome,
            "instruction": tr(INSTRUCTIONS[cur.kind]) if cur else None, "current": cur.kind.value if cur else None,
            "steps": [{"kind": s.kind.value, "state": s.state.value, "reason": s.reason} for s in self._steps],
        }

    def can_retry(self) -> bool:
        return self.finished and self.outcome in ("FAILED", "TIMED_OUT") and self.attempt < self.cfg.max_attempts

    def retry(self) -> None:
        if not self.can_retry():
            raise RuntimeError("No retry available")
        self.attempt += 1
        self._steps = [_Step(k) for k in self._sequence]  # same instructions again
        self.index, self.finished, self.outcome = 0, False, None

    # -- feeding -----------------------------------------------------------------------------------
    def feed(self, obs: Observation) -> dict:
        if self.finished:
            return self.progress()
        step = self._steps[self.index]
        if step.started_at is None:
            step.started_at = obs.t
        if obs.t - step.started_at > self.cfg.timeout_seconds:
            return self._end(step, State.TIMED_OUT, "Timed out before the action was seen.", "TIMED_OUT")
        if obs.face_count != 1 or obs.ear is None or obs.yaw is None:
            # Never guess: reset partial progress and wait for exactly one measurable face.
            step.closed_frames = step.held = 0
            step.reason = "Keep exactly one face clearly in view." if obs.face_count != 1 else "Face could not be measured."
            return self.progress()
        step.reason = None
        done = self._blink(step, obs) if step.kind == Kind.BLINK else self._turn(step, obs)
        if done:
            step.state = State.PASSED
            self.index += 1
            if self.index >= len(self._steps):
                self.finished, self.outcome = True, "PASSED"
        return self.progress()

    def _end(self, step: _Step, state: State, reason: str, outcome: str) -> dict:
        step.state, step.reason = state, reason
        self.finished, self.outcome = True, outcome
        return self.progress()

    def _blink(self, s: _Step, o: Observation) -> bool:
        c = self.cfg
        if abs(o.yaw) > max(c.neutral_band * 2, 0.3):  # head moved: eye geometry unreliable, do not count
            s.closed_frames = 0
            return False
        if o.ear >= c.ear_open:
            if s.saw_open and s.closed_frames >= c.min_closed_frames:
                return True  # open -> closed -> open
            s.saw_open, s.closed_frames = True, 0
        elif o.ear <= c.ear_closed and s.saw_open:
            s.closed_frames += 1
        return False

    def _turn(self, s: _Step, o: Observation) -> bool:
        c = self.cfg
        if not s.saw_neutral:
            s.saw_neutral = abs(o.yaw) <= c.neutral_band  # must start frontal, so a pre-turned head cannot pass
            return False
        # "left" for the user: image-right when the preview is mirrored, otherwise image-left.
        want = 1 if (s.kind == Kind.TURN_LEFT) == c.mirrored_display else -1
        s.held = s.held + 1 if o.yaw * want >= c.turn_threshold else 0
        return s.held >= c.hold_frames


def verdict_note(outcome: str | None) -> str:
    """Text for the verification explanation. Deliberately never claims liveness."""
    if outcome == "PASSED":
        return ("The requested movements were observed. This is supporting evidence only: it does not prove the face is "
                "live, because recordings and manipulated video can imitate movements.")
    if outcome == "TIMED_OUT":
        return "The challenge timed out, so no conclusion can be drawn."
    if outcome == "FAILED":
        return "The requested movements were not observed, so no conclusion can be drawn."
    return "No challenge was completed."
