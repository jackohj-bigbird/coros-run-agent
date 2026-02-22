from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import Activity, TrainingPlanItem


@dataclass
class WeeklySummary:
    week_start: date
    week_end: date
    run_count: int
    total_distance_km: float
    total_time_min: float
    avg_pace_min_per_km: float
    longest_run_km: float
    avg_hr: Optional[float]
    completion_rate: float


def _week_boundaries(anchor: Optional[date] = None) -> Tuple[date, date]:
    today = anchor or date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def build_weekly_summary(db: Session, anchor: Optional[date] = None) -> WeeklySummary:
    week_start, week_end = _week_boundaries(anchor)
    dt_start = datetime.combine(week_start, datetime.min.time())
    dt_end = datetime.combine(week_end + timedelta(days=1), datetime.min.time())

    activities = db.scalars(
        select(Activity).where(Activity.start_date >= dt_start, Activity.start_date < dt_end)
    ).all()

    runs = [a for a in activities if a.activity_type == "Run"]
    total_distance_km = sum(a.distance_m for a in runs) / 1000
    total_time_min = sum(a.moving_time_s for a in runs) / 60
    longest_run_km = max([a.distance_m for a in runs], default=0) / 1000

    if total_distance_km > 0:
        avg_pace_min_per_km = total_time_min / total_distance_km
    else:
        avg_pace_min_per_km = 0.0

    hr_values = [a.average_heartrate for a in runs if a.average_heartrate is not None]
    avg_hr = round(sum(hr_values) / len(hr_values), 1) if hr_values else None

    planned = db.scalars(
        select(TrainingPlanItem).where(
            TrainingPlanItem.plan_date >= week_start,
            TrainingPlanItem.plan_date <= week_end,
        )
    ).all()

    planned_count = len(planned)
    # Simplified completion: compare run count to planned count this week.
    completion_rate = min(1.0, len(runs) / planned_count) if planned_count else 0.0

    return WeeklySummary(
        week_start=week_start,
        week_end=week_end,
        run_count=len(runs),
        total_distance_km=round(total_distance_km, 2),
        total_time_min=round(total_time_min, 1),
        avg_pace_min_per_km=round(avg_pace_min_per_km, 2),
        longest_run_km=round(longest_run_km, 2),
        avg_hr=avg_hr,
        completion_rate=round(completion_rate, 2),
    )


def format_pace(min_per_km: float) -> str:
    if min_per_km <= 0:
        return "--"
    minutes = int(min_per_km)
    seconds = int(round((min_per_km - minutes) * 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}/km"
