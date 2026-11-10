"""Dataset management (Phase 4): owner-scoped, filesystem-backed, no database migration needed.

Layout:  <root>/<dataset_id>/dataset.json   metadata + one record per image (key = SHA-256 of the bytes)
         <root>/<dataset_id>/images/<sha256>.<jpg|png>
Safety:  * file names from clients are metadata only; paths are built from the content hash,
         * dataset ids must be 32 hex chars (no traversal), every operation checks the owner,
         * another user's dataset is reported as "not found", never as "forbidden",
         * identical images are rejected as duplicates (also prevents train/test leakage by copy),
         * deletion overwrites then unlinks every file (best effort; cannot defeat SSD wear levelling).
Single-process: a lock serialises writes. Run one backend worker or move metadata into the database.
Nothing here invents or downloads data: every image comes from an upload.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import threading
import uuid
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

LABELS = ("REAL", "FAKE")
_ID = re.compile(r"^[0-9a-f]{32}$")
_COLLECT_TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_TAG = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
EXT = {"jpeg": ".jpg", "png": ".png"}
MIN_PER_CLASS = 20
MAX_NAME = 80

# validator(filename, data) -> (sniffed_type, width, height); raises on invalid input. Injected so this module has no
# web-framework dependency (the API passes the same checks used for verification uploads).
Validator = Callable[[str | None, bytes], tuple[str, int, int]]


class DatasetError(ValueError):
    """Bad input. Message is safe to show to users."""


class DatasetNotFound(LookupError):
    pass


class DatasetConflict(DatasetError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _wipe(path: Path) -> None:
    try:
        size = path.stat().st_size
        with path.open("r+b") as f:
            f.write(b"\x00" * size); f.flush(); os.fsync(f.fileno())
    except OSError:
        pass
    path.unlink(missing_ok=True)


def _tag(value: str | None, what: str) -> str | None:
    if value is None or value == "":
        return None
    if not _TAG.match(value):
        raise DatasetError(f"{what} may only contain letters, digits, '_', '.', '-' (max 64). "
                           "Use a pseudonymous code, not a real name.")
    return value


class DatasetStore:
    def __init__(self, root: str | Path, max_datasets_per_user: int = 50, max_images: int = 20000,
                 max_dataset_bytes: int = 2 << 30):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_datasets, self.max_images, self.max_bytes = max_datasets_per_user, max_images, max_dataset_bytes
        self._lock = threading.RLock()

    # ---- internals -----------------------------------------------------------------------------------------------
    def _dir(self, dataset_id: str) -> Path:
        if not _ID.match(dataset_id or ""):
            raise DatasetNotFound("Dataset not found.")
        return self.root / dataset_id

    def _load(self, owner: str, dataset_id: str) -> dict:
        meta_path = self._dir(dataset_id) / "dataset.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            raise DatasetNotFound("Dataset not found.") from None
        if meta.get("owner") != str(owner):
            raise DatasetNotFound("Dataset not found.")
        return meta

    def _save(self, meta: dict) -> None:
        meta["updated_at"] = _now()
        d = self._dir(meta["id"])
        tmp = d / "dataset.json.tmp"
        tmp.write_text(json.dumps(meta, indent=1), encoding="utf-8")
        os.replace(tmp, d / "dataset.json")

    @staticmethod
    def _summary(meta: dict) -> dict:
        s = meta["samples"].values()
        c = Counter(x["label"] for x in s)
        col = meta.get("collect") or {}
        return {"id": meta["id"], "name": meta["name"], "description": meta["description"], "created_at": meta["created_at"],
                "updated_at": meta["updated_at"], "images": len(meta["samples"]), "real": c["REAL"], "fake": c["FAKE"],
                "unlabeled": c[None],
                "collect": {"enabled": bool(col.get("enabled")), "token": col.get("token") if col.get("enabled") else None,
                            "participants": len({x["identity"] for x in s if x.get("source") == "collect"})}}

    # ---- public collection links (collect.ekyc.mn-style data gathering) ----------------------------------------------
    def set_collection(self, owner: str, dataset_id: str, enabled: bool, rotate: bool = False) -> dict:
        """Turns the public collection link on/off. The token is a bearer capability: anyone with the link can ADD
        labelled recordings to this one dataset, nothing else. `rotate` issues a new token (old links stop working)."""
        import secrets
        with self._lock:
            meta = self._load(owner, dataset_id)
            col = meta.get("collect") or {}
            if enabled and (rotate or not col.get("token")):
                col["token"] = secrets.token_urlsafe(18)
                col["created_at"] = _now()
            col["enabled"] = enabled
            meta["collect"] = col
            self._save(meta)
            return self._summary(meta)

    def find_by_token(self, token: str) -> dict | None:
        """The dataset whose ENABLED collection link has this token, else None. Constant-time comparison."""
        import hmac
        if not token or not _COLLECT_TOKEN.match(token):
            return None
        for meta_path in self.root.glob("*/dataset.json"):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            col = meta.get("collect") or {}
            if col.get("enabled") and col.get("token") and hmac.compare_digest(col["token"], token):
                return meta
        return None

    # ---- CRUD ----------------------------------------------------------------------------------------------------
    def create(self, owner: str, name: str, description: str = "") -> dict:
        name = (name or "").strip()
        if not name or len(name) > MAX_NAME:
            raise DatasetError(f"Name is required (max {MAX_NAME} characters).")
        with self._lock:
            mine = self.list(owner)
            if len(mine) >= self.max_datasets:
                raise DatasetError(f"Dataset limit reached ({self.max_datasets}).")
            if any(m["name"].lower() == name.lower() for m in mine):
                raise DatasetConflict("You already have a dataset with this name.")
            ds_id = uuid.uuid4().hex
            (self.root / ds_id / "images").mkdir(parents=True)
            meta = {"id": ds_id, "owner": str(owner), "name": name, "description": (description or "")[:500],
                    "created_at": _now(), "updated_at": _now(), "samples": {}}
            self._save(meta)
            return self._summary(meta)

    def list(self, owner: str) -> list[dict]:
        out = []
        for p in sorted(self.root.glob("*/dataset.json")):
            try:
                meta = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if meta.get("owner") == str(owner):
                out.append(self._summary(meta))
        return sorted(out, key=lambda m: m["created_at"], reverse=True)

    def get(self, owner: str, dataset_id: str, offset: int = 0, limit: int = 50, label: str | None = None) -> dict:
        meta = self._load(owner, dataset_id)
        if label not in (None, "REAL", "FAKE", "UNLABELED"):
            raise DatasetError("label filter must be REAL, FAKE or UNLABELED.")
        items = [dict(sha256=k, **{kk: v for kk, v in s.items()}) for k, s in meta["samples"].items()
                 if label is None or (s["label"] or "UNLABELED") == label]
        items.sort(key=lambda s: (s["added_at"], s["sha256"]))
        offset, limit = max(0, offset), min(max(1, limit), 200)
        return {**self._summary(meta), "total_filtered": len(items), "offset": offset, "limit": limit,
                "items": items[offset:offset + limit]}

    def delete(self, owner: str, dataset_id: str) -> int:
        """Securely removes every file, then the folder. Returns the number of images removed."""
        with self._lock:
            meta = self._load(owner, dataset_id)
            d = self._dir(dataset_id)
            for p in d.rglob("*"):
                if p.is_file():
                    _wipe(p)
            shutil.rmtree(d, ignore_errors=True)
            return len(meta["samples"])

    # ---- images --------------------------------------------------------------------------------------------------
    def add_image(self, owner: str, dataset_id: str, filename: str | None, data: bytes, validate: Validator,
                  label: str | None = None, identity: str | None = None, group: str | None = None,
                  source: str | None = None) -> dict:
        import hashlib
        if label not in (None, *LABELS):
            raise DatasetError("label must be REAL or FAKE.")
        identity, group = _tag(identity, "Identity"), _tag(group, "Group")
        sniffed, w, h = validate(filename, data)            # raises for anything that is not a real, safe image
        if sniffed not in EXT:
            raise DatasetError("Only JPEG and PNG images can be added to a dataset.")
        sha = hashlib.sha256(data).hexdigest()
        with self._lock:
            meta = self._load(owner, dataset_id)
            if sha in meta["samples"]:
                raise DatasetConflict("This exact image is already in the dataset.")
            if len(meta["samples"]) >= self.max_images:
                raise DatasetError(f"Dataset image limit reached ({self.max_images}).")
            if sum(s["size"] for s in meta["samples"].values()) + len(data) > self.max_bytes:
                raise DatasetError("Dataset size limit reached.")
            ext = EXT[sniffed]
            path = self._dir(dataset_id) / "images" / f"{sha}{ext}"
            tmp = path.with_suffix(".part")
            tmp.write_bytes(data)
            os.replace(tmp, path)
            rec = {"ext": ext, "label": label, "identity": identity, "group": group, "size": len(data),
                   "width": w, "height": h, "original_name": re.sub(r"[^\w.\- ]", "_", os.path.basename(filename or "image"))[:120],
                   "added_at": _now()}
            if source:
                rec["source"] = source
            meta["samples"][sha] = rec
            self._save(meta)
            return {"sha256": sha, **rec}

    def _sample(self, meta: dict, sha: str) -> dict:
        if not _SHA.match(sha or "") or sha not in meta["samples"]:
            raise DatasetNotFound("Image not found.")
        return meta["samples"][sha]

    def update_image(self, owner: str, dataset_id: str, sha: str, *, label: str | None = ..., identity: str | None = ...,
                     group: str | None = ...) -> dict:  # type: ignore[assignment]
        """Only the fields passed are changed; pass label=None to clear a label."""
        with self._lock:
            meta = self._load(owner, dataset_id)
            s = self._sample(meta, sha)
            if label is not ...:
                if label not in (None, *LABELS):
                    raise DatasetError("label must be REAL or FAKE.")
                s["label"] = label
            if identity is not ...:
                s["identity"] = _tag(identity, "Identity")
            if group is not ...:
                s["group"] = _tag(group, "Group")
            self._save(meta)
            return {"sha256": sha, **s}

    def remove_image(self, owner: str, dataset_id: str, sha: str) -> None:
        with self._lock:
            meta = self._load(owner, dataset_id)
            s = self._sample(meta, sha)
            _wipe(self._dir(dataset_id) / "images" / f"{sha}{s['ext']}")
            del meta["samples"][sha]
            self._save(meta)

    def read_image(self, owner: str, dataset_id: str, sha: str) -> tuple[bytes, str]:
        meta = self._load(owner, dataset_id)
        s = self._sample(meta, sha)
        return (self._dir(dataset_id) / "images" / f"{sha}{s['ext']}").read_bytes(), s["ext"]

    # ---- statistics / validation / export ------------------------------------------------------------------------
    def stats(self, owner: str, dataset_id: str) -> dict:
        meta = self._load(owner, dataset_id)
        s = list(meta["samples"].values())
        labels = Counter(x["label"] or "UNLABELED" for x in s)
        ids = Counter(x["identity"] for x in s if x["identity"])
        ids_by_label = {lab: len({x["identity"] for x in s if x["identity"] and x["label"] == lab}) for lab in LABELS}
        return {
            "images": len(s), "labels": {"REAL": labels["REAL"], "FAKE": labels["FAKE"], "UNLABELED": labels["UNLABELED"]},
            "identities": len(ids), "images_without_identity": sum(1 for x in s if not x["identity"]),
            "identities_by_label": ids_by_label, "max_images_per_identity": max(ids.values(), default=0),
            "total_bytes": sum(x["size"] for x in s),
            "min_side_px": min((min(x["width"], x["height"]) for x in s), default=None),
            "max_side_px": max((max(x["width"], x["height"]) for x in s), default=None),
        }

    def validate(self, owner: str, dataset_id: str, min_per_class: int = MIN_PER_CLASS) -> dict:
        """Is this dataset fit to train on? `ready` is False while any problem exists. Re-hashes every file."""
        import hashlib
        meta = self._load(owner, dataset_id)
        st = self.stats(owner, dataset_id)
        problems: list[str] = []
        warnings: list[str] = []
        for sha, s in meta["samples"].items():
            p = self._dir(dataset_id) / "images" / f"{sha}{s['ext']}"
            if not p.is_file():
                problems.append(f"Image file missing: {sha[:12]}")
            elif hashlib.sha256(p.read_bytes()).hexdigest() != sha:
                problems.append(f"Image file changed on disk (hash mismatch): {sha[:12]}")
        for lab, name in (("REAL", "real"), ("FAKE", "fake")):
            if st["labels"][lab] < min_per_class:
                problems.append(f"Need at least {min_per_class} {name} images, found {st['labels'][lab]}.")
        if st["labels"]["UNLABELED"]:
            problems.append(f"{st['labels']['UNLABELED']} image(s) have no REAL/FAKE label.")
        if st["images_without_identity"]:
            warnings.append(f"{st['images_without_identity']} image(s) have no identity code, so an identity-disjoint "
                            "train/test split is impossible for them. Frames of the same person in train and test inflate results.")
        elif 0 < st["identities"] < 3:
            warnings.append("Fewer than 3 identities: train, validation and test cannot all be identity-disjoint.")
        r, f = st["labels"]["REAL"], st["labels"]["FAKE"]
        if r and f and max(r, f) / min(r, f) > 4:
            warnings.append(f"Classes are imbalanced ({r} real vs {f} fake); the trainer will weight the loss, "
                            "but accuracy alone will mislead.")
        return {"ready": not problems, "problems": problems, "warnings": warnings, "stats": st}

    def export_zip(self, owner: str, dataset_id: str, transform=None, preprocessing: dict | None = None) -> tuple[bytes, dict]:
        """manifest.csv (path,label,sha256,identity,group) + images/, directly usable by ai/faceguard_ai/data.py.
        Unlabeled images are left out and counted. Held in memory: bounded by max_dataset_bytes.

        `transform(bytes) -> (bytes, ext) | None` rewrites each image (e.g. face crop); None skips that image.
        `preprocessing` is written to preprocessing.json so the trained model can be registered with the same setting."""
        meta = self._load(owner, dataset_id)
        rows = [(sha, s) for sha, s in sorted(meta["samples"].items()) if s["label"]]
        skipped = len(meta["samples"]) - len(rows)
        untransformed = 0
        manifest = io.StringIO()
        w = csv.writer(manifest)
        w.writerow(["path", "label", "sha256", "identity", "group"])
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
            for sha, s in rows:
                src = self._dir(dataset_id) / "images" / f"{sha}{s['ext']}"
                if transform is None:
                    rel = f"images/{sha}{s['ext']}"
                    z.write(src, rel)
                else:
                    out = transform(src.read_bytes())
                    if out is None:
                        untransformed += 1
                        continue
                    data, ext = out
                    rel = f"images/{sha}{ext}"
                    z.writestr(rel, data)
                # sha256 identifies the SOURCE image (dedup / provenance), also for transformed crops
                w.writerow([rel, s["label"].lower(), sha, s["identity"] or "", s["group"] or ""])
            z.writestr("manifest.csv", manifest.getvalue())
            if preprocessing is not None:
                z.writestr("preprocessing.json", json.dumps(preprocessing, indent=2))
        info = {"exported": len(rows) - untransformed, "skipped_unlabeled": skipped}
        if transform is not None:
            info["skipped_no_single_face"] = untransformed
        return buf.getvalue(), info
