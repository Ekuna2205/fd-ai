from fastapi import APIRouter

from app.api.routes import admin, auth, collect, dashboard, datasets, face, health, models, reports, uploads, users, verifications

api_router = APIRouter(prefix="/api")
for r in (health.router, auth.router, users.router, dashboard.router, face.router, uploads.router, verifications.router, datasets.router,
          reports.router, admin.router, models.router, collect.router):
    api_router.include_router(r)
