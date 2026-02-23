from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import router
from app.core.config import settings
from app.core.database import Base, engine
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
    try:
        Base.metadata.create_all(bind=engine)
        # Backward-compatible schema fix for existing Postgres tables.
        if engine.dialect.name.startswith("postgresql"):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE IF EXISTS activities "
                        "ALTER COLUMN strava_activity_id TYPE BIGINT"
                    )
                )
    except Exception:
        # Keep API alive even if DB is temporarily unavailable during boot.
        pass
    if settings.enable_scheduler:
        scheduler_service.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    if settings.enable_scheduler:
        scheduler_service.stop()
