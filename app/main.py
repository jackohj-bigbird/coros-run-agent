from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.scheduler import SchedulerService

app = FastAPI(title="COROS Running Agent", version="0.1.0")

if settings.cors_origins.strip() == "*":
    allow_origins = ["*"]
else:
    allow_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

scheduler_service = SchedulerService()


@app.on_event("startup")
def on_startup() -> None:
    if settings.enable_scheduler:
        scheduler_service.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    if settings.enable_scheduler:
        scheduler_service.stop()
