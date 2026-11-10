import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile

from app.api.deps import CurrentUser, DbSession, client_ip, require_roles
from app.core.config import get_settings
from app.core.rate_limit import user_rate_limit
from app.models.enums import RoleName
from app.models.user import User
from app.schemas.history import ModelDetail, ModelOut
from app.services import model_service
from app.services.face import media

router = APIRouter(prefix="/models", tags=["models"])
Manager = Annotated[User, Depends(require_roles(RoleName.ADMINISTRATOR, RoleName.RESEARCHER))]


@router.get("", response_model=list[ModelOut])
def list_models(db: DbSession, _: CurrentUser) -> list[ModelOut]:
    return model_service.list_models(db)


@router.get("/{model_id}", response_model=ModelDetail)
def get_model(model_id: uuid.UUID, db: DbSession, _: CurrentUser) -> ModelDetail:
    return model_service.detail(db, model_id)


@router.post("/{model_id}/activate", response_model=ModelOut)
def activate(model_id: uuid.UUID, request: Request, db: DbSession, user: Manager) -> ModelOut:
    """409 with the exact reasons unless the model is trained, has its ONNX file, and a valid identity-disjoint evaluation."""
    return model_service.activate(db, user, client_ip(request), model_id)


@router.post("/{model_id}/deactivate", response_model=ModelOut)
def deactivate(model_id: uuid.UUID, request: Request, db: DbSession, user: Manager) -> ModelOut:
    return model_service.deactivate(db, user, client_ip(request), model_id)


@router.post("", response_model=ModelOut, status_code=201,
             dependencies=[Depends(user_rate_limit("rate_limit_dataset_per_minute"))])
def register(request: Request, db: DbSession, user: Manager, onnx: UploadFile = File(...),
             test_metrics: UploadFile = File(...), split_report: UploadFile = File(...),
             name: str = Form(..., max_length=64), version: str = Form(..., max_length=64),
             architecture: str = Form("SmallCNN", max_length=120), description: str | None = Form(None, max_length=2000),
             input_crop: Literal["full", "face"] = Form("full")) -> ModelOut:
    """Registers a finished training run from its three output files. Validated with ONNX Runtime; never activated."""
    s = get_settings()
    return model_service.register_upload(
        db, user, client_ip(request), onnx_data=media.read_limited(onnx, s.max_model_mb * (1 << 20)),
        metrics_data=media.read_limited(test_metrics, 1 << 20), split_data=media.read_limited(split_report, 1 << 20),
        name=name.strip(), version=version.strip(), architecture=architecture.strip(), description=description,
        input_crop=input_crop)


@router.delete("/{model_id}", status_code=204)
def delete(model_id: uuid.UUID, request: Request, db: DbSession, user: Manager) -> Response:
    """Deletes an inactive model and its file. Existing verification results keep the model label they were given."""
    model_service.delete(db, user, client_ip(request), model_id)
    return Response(status_code=204)
