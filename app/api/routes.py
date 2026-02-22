from datetime import date
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, engine, get_db
from app.core.models import Activity, TrainingPlanItem
from app.services.analysis import build_weekly_summary, format_pace
from app.services.chat_agent import ChatAgent
from app.services.planner import generate_half_marathon_plan
from app.services.reminder import EmailReminderService
from app.services.strava import StravaService

router = APIRouter()
strava_service = StravaService()
mailer = EmailReminderService()
chat_agent = ChatAgent()


class PlanSetupRequest(BaseModel):
    start_date: date = Field(default_factory=date.today)
    race_date: date
    target_time_min: float = 100.0


class AskRequest(BaseModel):
    question: str


class StravaWebhookEvent(BaseModel):
    object_type: str
    object_id: int
    owner_id: int
    aspect_type: str
    subscription_id: Optional[int] = None
    event_time: Optional[int] = None
    updates: Optional[Dict[str, Any]] = None


@router.get("/health")
def health() -> dict[str, str]:
    Base.metadata.create_all(bind=engine)
    return {"status": "ok"}


@router.post("/plan/setup")
def plan_setup(payload: PlanSetupRequest, db: Session = Depends(get_db)) -> dict[str, int]:
    inserted = generate_half_marathon_plan(
        db=db,
        start_date=payload.start_date,
        race_date=payload.race_date,
        target_hm_time_min=payload.target_time_min,
    )
    return {"inserted": inserted}


@router.get("/plan")
def get_plan(limit: int = 30, db: Session = Depends(get_db)) -> List[Dict[str, Union[str, float]]]:
    items = db.scalars(
        select(TrainingPlanItem).order_by(TrainingPlanItem.plan_date.asc()).limit(limit)
    ).all()
    return [
        {
            "date": str(item.plan_date),
            "weekday": item.weekday,
            "type": item.session_type,
            "distance_km": item.planned_distance_km,
            "pace": item.target_pace_min_per_km,
            "desc": item.description,
            "status": item.status,
        }
        for item in items
    ]


@router.get("/activities/recent")
def get_recent_activities(limit: int = 10, db: Session = Depends(get_db)) -> List[Dict[str, Union[str, float, int]]]:
    activities = db.scalars(
        select(Activity).order_by(Activity.start_date.desc()).limit(limit)
    ).all()
    result: List[Dict[str, Union[str, float, int]]] = []
    for item in activities:
        pace_min_per_km = 0.0
        if item.distance_m > 0:
            pace_min_per_km = (item.moving_time_s / 60.0) / (item.distance_m / 1000.0)
        result.append(
            {
                "id": item.strava_activity_id,
                "name": item.name,
                "type": item.activity_type,
                "start_date": item.start_date.isoformat(),
                "distance_km": round(item.distance_m / 1000.0, 2),
                "moving_time_min": round(item.moving_time_s / 60.0, 1),
                "avg_pace": format_pace(pace_min_per_km),
            }
        )
    return result


@router.post("/sync/strava")
def sync_strava(db: Session = Depends(get_db)) -> Dict[str, Union[int, str]]:
    if not strava_service.is_configured():
        raise HTTPException(status_code=400, detail="Strava is not configured. Fill STRAVA_* in .env.")

    activities = strava_service.fetch_recent_activities()
    inserted = strava_service.upsert_run_activities(db, activities)
    return {"inserted": inserted, "message": "sync completed"}


@router.get("/webhook/strava")
def strava_webhook_verify(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
) -> Dict[str, str]:
    if hub_mode != "subscribe":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid hub.mode")
    if not settings.strava_webhook_verify_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="STRAVA_WEBHOOK_VERIFY_TOKEN is not set")
    if hub_verify_token != settings.strava_webhook_verify_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid verify token")
    return {"hub.challenge": hub_challenge}


@router.post("/webhook/strava")
def strava_webhook_event(payload: StravaWebhookEvent, db: Session = Depends(get_db)) -> Dict[str, Union[str, int]]:
    if payload.object_type != "activity":
        return {"status": "ignored", "reason": "non-activity event"}
    if settings.strava_athlete_id and str(payload.owner_id) != settings.strava_athlete_id:
        return {"status": "ignored", "reason": "owner_id mismatch"}
    if payload.aspect_type == "delete":
        return {"status": "ignored", "reason": "activity deleted"}

    try:
        activity = strava_service.fetch_activity_by_id(payload.object_id)
        inserted = strava_service.upsert_run_activities(db, [activity])
        return {"status": "ok", "inserted": inserted}
    except Exception:
        # Keep webhook endpoint resilient to transient upstream/API errors.
        return {"status": "error", "inserted": 0}


@router.post("/webhook/strava/register")
def register_strava_webhook() -> Dict[str, Union[str, int]]:
    if not strava_service.is_configured():
        raise HTTPException(status_code=400, detail="Strava is not configured. Fill STRAVA_* in .env.")
    if not settings.strava_webhook_callback_url or not settings.strava_webhook_verify_token:
        raise HTTPException(
            status_code=400,
            detail="Set STRAVA_WEBHOOK_CALLBACK_URL and STRAVA_WEBHOOK_VERIFY_TOKEN in .env.",
        )

    result = strava_service.create_webhook_subscription(
        callback_url=settings.strava_webhook_callback_url,
        verify_token=settings.strava_webhook_verify_token,
    )
    return {
        "message": "subscription created",
        "id": result.get("id", 0),
    }


@router.get("/webhook/strava/subscriptions")
def list_strava_webhooks() -> Dict[str, List[Dict[str, Any]]]:
    if not strava_service.is_configured():
        raise HTTPException(status_code=400, detail="Strava is not configured. Fill STRAVA_* in .env.")
    subs = strava_service.list_webhook_subscriptions()
    return {"subscriptions": subs}


@router.delete("/webhook/strava/subscriptions/{subscription_id}")
def delete_strava_webhook(subscription_id: int) -> Dict[str, Union[str, int]]:
    if not strava_service.is_configured():
        raise HTTPException(status_code=400, detail="Strava is not configured. Fill STRAVA_* in .env.")
    result = strava_service.delete_webhook_subscription(subscription_id)
    return {"message": "subscription deleted", "deleted_id": int(result["deleted_id"])}


@router.get("/summary/weekly")
def weekly_summary(db: Session = Depends(get_db)) -> Dict[str, Union[str, int, float, Optional[float]]]:
    summary = build_weekly_summary(db, anchor=date.today())
    return {
        "week_start": str(summary.week_start),
        "week_end": str(summary.week_end),
        "run_count": summary.run_count,
        "total_distance_km": summary.total_distance_km,
        "total_time_min": summary.total_time_min,
        "avg_pace": format_pace(summary.avg_pace_min_per_km),
        "longest_run_km": summary.longest_run_km,
        "avg_hr": summary.avg_hr,
        "completion_rate": summary.completion_rate,
    }


@router.post("/chat")
def ask_agent(payload: AskRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    answer = chat_agent.ask(db, payload.question)
    return {"answer": answer}


@router.post("/reminder/test")
def send_test_email() -> dict[str, str]:
    if not mailer.is_configured():
        raise HTTPException(status_code=400, detail="Email is not configured. Fill SMTP_* and EMAIL_* in .env.")

    mailer.send_email(
        subject="[跑步Agent] 测试邮件",
        body="这是一封测试邮件。你的跑步提醒通道已打通。",
    )
    return {"message": "test email sent"}
