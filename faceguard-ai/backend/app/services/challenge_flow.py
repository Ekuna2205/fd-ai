"""Server-side challenge flow (Phase 6): issue a signed challenge, then judge the *server's own* measurements.

The browser never reports "I blinked". It uploads a short recording; the backend measures landmarks itself
(challenge_video.py) and this module decides. A challenge token is:
  * HMAC-SHA256 signed (cannot be forged or edited: the required sequence is inside it),
  * bound to one user, short-lived, and single-use (NonceStore).

What a PASSED outcome means: the requested movements were observed in the recording. It is NOT proof of a live person
(replays, deepfakes and puppeted photos can imitate movements) and it never produces REAL. `describe()` keeps the
five concepts apart: face detected / quality passed / challenge completed / liveness assessed / AI classification.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass, field

from app.services import challenge as ch
from app.core.i18n import tr

TOKEN_VERSION = 1
DEFAULT_TTL_SECONDS = 120          # time allowed between issuing and uploading
MIN_OBSERVATIONS = 5               # fewer measurable frames than this can never pass
MAX_OBSERVATIONS = 2000


class TokenError(ValueError):
    """Invalid, expired, foreign or already-used challenge token. Message is safe to show to the user."""


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(secret: str, body: str) -> str:
    return _b64(hmac.new(secret.encode(), b"faceguard-challenge-v1." + body.encode(), hashlib.sha256).digest())


@dataclass
class NonceStore:
    """Remembers consumed nonces until they expire. In-process: with several backend workers, replace it with a shared
    store (e.g. a database table or Redis). The interface is only `consume`."""
    _seen: dict[str, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def consume(self, nonce: str, expires_at: float, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self._lock:
            for k in [k for k, exp in self._seen.items() if exp < now]:
                del self._seen[k]
            if nonce in self._seen:
                return False
            self._seen[nonce] = expires_at
            return True


def issue(secret: str, user_id: str, cfg: ch.Config | None = None, *, seed: int | None = None,
          now: float | None = None, ttl: int = DEFAULT_TTL_SECONDS) -> tuple[str, dict]:
    """Returns (token, public view). The public view is what the UI shows: instructions, never the signature."""
    cfg = cfg or ch.Config()
    now = time.time() if now is None else now
    seq = ch.make_sequence(cfg, seed)
    payload = {"v": TOKEN_VERSION, "uid": str(user_id), "seq": [k.value for k in seq],
               "iat": int(now), "exp": int(now) + ttl, "nonce": secrets.token_hex(16),
               "timeout": cfg.timeout_seconds, "mirrored": cfg.mirrored_display}
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    token = f"{body}.{_sign(secret, body)}"
    return token, public_view(payload)


def public_view(p: dict) -> dict:
    return {"expires_at": p["exp"], "steps": [{"kind": k, "instruction": tr(ch.INSTRUCTIONS[ch.Kind(k)])} for k in p["seq"]],
            "step_timeout_seconds": p["timeout"], "max_recording_seconds": int(p["timeout"] * len(p["seq"]) + 4),
            "mirrored_display": p["mirrored"]}


def open_token(secret: str, token: str, user_id: str, nonces: NonceStore, *, now: float | None = None) -> dict:
    """Verifies signature, owner and expiry, then burns the nonce. Raises TokenError on any problem."""
    now = time.time() if now is None else now
    try:
        body, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, _sign(secret, body)):
            raise TokenError("The challenge is not valid.")
        p = json.loads(_unb64(body))
        if p.get("v") != TOKEN_VERSION or not isinstance(p.get("seq"), list) or not p["seq"]:
            raise TokenError("The challenge is not valid.")
        [ch.Kind(k) for k in p["seq"]]
    except TokenError:
        raise
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise TokenError("The challenge is not valid.") from None
    if p["uid"] != str(user_id):
        raise TokenError("The challenge is not valid.")        # deliberately the same message as a forged token
    if now > p["exp"]:
        raise TokenError("The challenge has expired. Start a new one.")
    if not nonces.consume(p["nonce"], p["exp"], now):
        raise TokenError("This challenge was already used. Start a new one.")
    return p


def evaluate(payload: dict, observations: list[ch.Observation]) -> dict:
    """Runs the engine over server-measured observations. Single attempt: a retry needs a NEW token."""
    if len(observations) > MAX_OBSERVATIONS:
        raise ValueError("Too many observations.")
    seq = [ch.Kind(k) for k in payload["seq"]]
    cfg = ch.Config(sequence_length=len(seq), timeout_seconds=float(payload["timeout"]), max_attempts=1,
                    mirrored_display=bool(payload["mirrored"]))
    measurable = [o for o in observations if o.face_count == 1 and o.ear is not None and o.yaw is not None]
    session = ch.ChallengeSession(cfg, seq)
    if len(measurable) >= MIN_OBSERVATIONS:
        for o in sorted(observations, key=lambda o: o.t):
            session.feed(o)
            if session.finished:
                break
    outcome = session.outcome or "FAILED"       # recording ended before every step was seen
    return {"outcome": outcome, "progress": session.progress(), "frames_total": len(observations),
            "frames_measurable": len(measurable), "note": tr(ch.verdict_note(outcome))}


def describe(*, face_detected: bool, quality_passed: bool | None, challenge_outcome: str | None,
             model_status: str | None = None) -> dict:
    """The five separate claims. `liveness_assessed` and `ai_classification_available` are True only when an active,
    validated anti-spoofing model scored the recording (`model_status` = its REAL/FAKE/UNCERTAIN result).
    A passed challenge never sets them."""
    scored = model_status is not None
    if not scored:
        statement = "Challenge movements are supporting evidence only. Liveness has NOT been verified."
    elif model_status == "REAL":
        statement = "The anti-spoofing model and the challenge both support a live person."
    elif model_status == "FAKE":
        statement = "The anti-spoofing model indicates a presentation attack."
    else:
        statement = "The anti-spoofing model scored the recording, but the evidence is not conclusive."
    return {
        "face_detected": face_detected,
        "image_quality_passed": quality_passed,
        "challenge_completed": challenge_outcome == "PASSED",
        "challenge_outcome": challenge_outcome,
        "liveness_assessed": scored,
        "ai_classification_available": scored,
        "statement": tr(statement),
    }
