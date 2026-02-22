from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.models import Activity, TrainingPlanItem
from app.services.analysis import build_weekly_summary


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_weekly_summary_basic() -> None:
    db = _session()
    db.add(
        Activity(
            strava_activity_id=1,
            name="Easy Run",
            activity_type="Run",
            start_date=datetime(2026, 2, 24, 6, 30),
            distance_m=10000,
            moving_time_s=3000,
            elapsed_time_s=3200,
            total_elevation_gain_m=50,
            average_heartrate=150,
            max_heartrate=170,
            average_speed_mps=3.3,
            raw_json="{}",
        )
    )
    db.add(
        TrainingPlanItem(
            plan_date=date(2026, 2, 24),
            weekday="Tuesday",
            session_type="easy",
            description="Easy run",
            planned_distance_km=8,
            target_pace_min_per_km="5:15/km",
            status="planned",
        )
    )
    db.commit()

    summary = build_weekly_summary(db, anchor=date(2026, 2, 25))
    assert summary.run_count == 1
    assert summary.total_distance_km == 10.0
    assert summary.longest_run_km == 10.0
    assert summary.completion_rate == 1.0
