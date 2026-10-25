"""All HTTP routes, grouped by domain. main.py mounts `router` under /api."""

from fastapi import APIRouter

from app.api.routes import admin, analytics, data, simulation, system

router = APIRouter()
for module in (system, data, analytics, simulation, admin):
    router.include_router(module.router)
