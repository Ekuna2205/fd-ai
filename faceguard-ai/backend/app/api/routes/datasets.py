"""Dataset management API (Phase 4). Every dataset belongs to one user; others get 404. Writers: administrator and
researcher. Images are validated by content (magic bytes + decode), stored under their SHA-256, never by client name."""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import DbSession, client_ip, require_roles
from app.core.config import get_settings
from app.core.errors import AppError, Conflict, NotFound
from app.core.rate_limit import user_rate_limit
from app.models.enums import RoleName
from app.models.user import User
from app.services import audit_service
from app.services import dataset_store as store_mod
from app.services.face import media
from app.core.i18n import tr_list

router = APIRouter(prefix="/datasets", tags=["datasets"],
                   dependencies=[Depends(user_rate_limit("rate_limit_dataset_per_minute"))])
Manager = Annotated[User, Depends(require_roles(RoleName.ADMINISTRATOR, RoleName.RESEARCHER))]


@lru_cache
def get_store() -> store_mod.DatasetStore:
    return store_mod.DatasetStore(Path(get_settings().data_dir) / "datasets")


@contextmanager
def _mapped():
    """Domain errors -> HTTP errors with user-safe messages."""
    try:
        yield
    except store_mod.DatasetNotFound as e:
        raise NotFound(str(e)) from None
    except store_mod.DatasetConflict as e:
        raise Conflict(str(e)) from None
    except store_mod.DatasetError as e:
        raise AppError(str(e), 422) from None


def _validator(filename: str | None, data: bytes):
    sniffed = media.validate("image", filename, data)
    h, w = media.decode_image(data).shape[:2]
    return sniffed, w, h


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=store_mod.MAX_NAME)
    description: str = Field("", max_length=500)


class ImagePatch(BaseModel):
    label: Literal["REAL", "FAKE"] | None = None
    identity: str | None = Field(None, max_length=64)
    group: str | None = Field(None, max_length=64)


@router.post("", status_code=201)
def create(body: DatasetCreate, user: Manager, db: DbSession, request: Request) -> dict:
    with _mapped():
        d = get_store().create(str(user.id), body.name, body.description)
    audit_service.record(db, "dataset.create", user_id=user.id, ip=client_ip(request), entity_type="dataset", entity_id=d["id"])
    db.commit()
    return d


@router.get("")
def list_datasets(user: Manager) -> list[dict]:
    return get_store().list(str(user.id))


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str, user: Manager, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                label: Literal["REAL", "FAKE", "UNLABELED"] | None = None) -> dict:
    with _mapped():
        return get_store().get(str(user.id), dataset_id, offset, limit, label)


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: str, user: Manager, db: DbSession, request: Request) -> Response:
    with _mapped():
        n = get_store().delete(str(user.id), dataset_id)
    audit_service.record(db, "dataset.delete", user_id=user.id, ip=client_ip(request), entity_type="dataset",
                         entity_id=dataset_id, details={"images": n})
    db.commit()
    return Response(status_code=204)


@router.post("/{dataset_id}/images", status_code=201)
def add_image(dataset_id: str, user: Manager, file: UploadFile = File(...), label: Annotated[Literal["REAL", "FAKE"] | None, Form()] = None,
              identity: Annotated[str | None, Form()] = None, group: Annotated[str | None, Form()] = None) -> dict:
    data = media.read_limited(file, get_settings().max_image_mb * (1 << 20))
    with _mapped():
        return get_store().add_image(str(user.id), dataset_id, file.filename, data, _validator, label, identity, group)


@router.patch("/{dataset_id}/images/{sha256}")
def patch_image(dataset_id: str, sha256: str, body: ImagePatch, user: Manager) -> dict:
    changes = {k: getattr(body, k) for k in body.model_fields_set}  # only fields the client actually sent
    with _mapped():
        return get_store().update_image(str(user.id), dataset_id, sha256, **changes)


@router.delete("/{dataset_id}/images/{sha256}", status_code=204)
def delete_image(dataset_id: str, sha256: str, user: Manager) -> Response:
    with _mapped():
        get_store().remove_image(str(user.id), dataset_id, sha256)
    return Response(status_code=204)


@router.get("/{dataset_id}/images/{sha256}/file")
def image_file(dataset_id: str, sha256: str, user: Manager) -> Response:
    with _mapped():
        data, ext = get_store().read_image(str(user.id), dataset_id, sha256)
    return Response(data, media_type="image/png" if ext == ".png" else "image/jpeg",
                    headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/{dataset_id}/stats")
def stats(dataset_id: str, user: Manager) -> dict:
    with _mapped():
        return get_store().stats(str(user.id), dataset_id)


@router.get("/{dataset_id}/validation")
def validation(dataset_id: str, user: Manager, min_per_class: int = Query(store_mod.MIN_PER_CLASS, ge=0, le=100000)) -> dict:
    with _mapped():
        out = get_store().validate(str(user.id), dataset_id, min_per_class)
    return {**out, "problems": tr_list(out["problems"]), "warnings": tr_list(out["warnings"])}


def _face_crop_transform(margin: float):
    """Same detector and crop function the API uses at inference time, so training and serving inputs match."""
    import cv2

    from app.services.face.detector import get_detector
    from app.services.inference import crop_face

    def transform(data: bytes):
        bgr = media.decode_image(data)
        faces = get_detector().detect(bgr).faces
        if len(faces) != 1:
            return None
        ok, png = cv2.imencode(".png", crop_face(bgr, faces[0], margin))  # lossless: keep the spoof cues intact
        return (png.tobytes(), ".png") if ok else None
    return transform


@router.get("/{dataset_id}/export")
def export(dataset_id: str, user: Manager, db: DbSession, request: Request,
           crop: Literal["full", "face"] = Query("full", description="face = one square face crop per image"),
           face_margin: float = Query(0.4, ge=0, le=2)) -> Response:
    transform = _face_crop_transform(face_margin) if crop == "face" else None
    prep = {"crop": crop, "face_margin": face_margin}
    with _mapped():
        blob, info = get_store().export_zip(str(user.id), dataset_id, transform, prep)
    audit_service.record(db, "dataset.export", user_id=user.id, ip=client_ip(request), entity_type="dataset",
                         entity_id=dataset_id, details={**info, "crop": crop})
    db.commit()
    headers = {"Content-Disposition": f'attachment; filename="dataset-{dataset_id[:8]}{"-faces" if crop == "face" else ""}.zip"',
               "Cache-Control": "private, no-store", "X-Exported-Images": str(info["exported"]),
               "X-Skipped-Unlabeled": str(info["skipped_unlabeled"])}
    if "skipped_no_single_face" in info:
        headers["X-Skipped-No-Face"] = str(info["skipped_no_single_face"])
    return Response(blob, media_type="application/zip", headers=headers)


class CollectionUpdate(BaseModel):
    enabled: bool
    rotate: bool = False  # issue a new link; the old one stops working


@router.put("/{dataset_id}/collect")
def set_collection(dataset_id: str, body: CollectionUpdate, user: Manager, db: DbSession, request: Request) -> dict:
    """Public collection link for this dataset: anyone with the link can add labelled recordings (and nothing else)."""
    with _mapped():
        d = get_store().set_collection(str(user.id), dataset_id, body.enabled, body.rotate)
    audit_service.record(db, "dataset.collect_link", user_id=user.id, ip=client_ip(request), entity_type="dataset",
                         entity_id=dataset_id, details={"enabled": body.enabled, "rotated": body.rotate})  # never the token
    db.commit()
    return d
