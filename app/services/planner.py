from datetime import date, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.models import TrainingPlanItem

RUN_DAY_MAP = {
    1: "Tuesday",
    3: "Thursday",
    5: "Saturday",
    6: "Sunday",
}


def _pace_windows(target_hm_time_min: float) -> dict[str, str]:
    race_pace = target_hm_time_min / 21.0975

    def to_pace(v: float) -> str:
        m = int(v)
        s = int(round((v - m) * 60))
        if s == 60:
            m += 1
            s = 0
        return f"{m}:{s:02d}/km"

    return {
        "easy": to_pace(race_pace + 0.7),
        "steady": to_pace(race_pace + 0.35),
        "tempo": to_pace(race_pace + 0.1),
        "interval": to_pace(max(3.5, race_pace - 0.2)),
        "race": to_pace(race_pace),
    }


def _next_weekday(current: date, target_weekday: int) -> date:
    days_ahead = (target_weekday - current.weekday()) % 7
    return current + timedelta(days=days_ahead)


def generate_half_marathon_plan(
    db: Session,
    start_date: date,
    race_date: date,
    target_hm_time_min: float = 100.0,
) -> int:
    if race_date <= start_date:
        raise ValueError("race_date must be after start_date")

    db.execute(delete(TrainingPlanItem).where(TrainingPlanItem.plan_date >= start_date))

    weeks = max(1, ((race_date - start_date).days // 7) + 1)
    paces = _pace_windows(target_hm_time_min)
    inserted = 0
    race_added = False

    base_long_run = 12.0

    for week in range(weeks):
        week_start = start_date + timedelta(days=week * 7)
        weeks_to_race = max(0, (race_date - week_start).days // 7)
        long_run = min(21.0, base_long_run + week * 1.2)

        # Taper in last 2 weeks.
        if weeks_to_race == 1:
            long_run *= 0.75
        elif weeks_to_race == 0:
            long_run = 8.0

        templates = {
            1: ("easy", 8.0, f"轻松跑 {8}km，跑后做4组加速跑", paces["easy"]),
            3: (
                "interval",
                10.0,
                "间歇训练：热身2km + 5x1km(间歇配速) + 放松2km",
                paces["interval"],
            ),
            5: ("steady", 8.0 + min(week, 4), "稳态跑，控制呼吸，可完整说短句", paces["steady"]),
            6: ("long", round(long_run, 1), "长距离慢跑，后半程稍提速", paces["easy"]),
        }

        for wd, weekday_name in RUN_DAY_MAP.items():
            plan_date = _next_weekday(week_start, wd)
            if plan_date < start_date or plan_date > race_date:
                continue

            session_type, planned_km, description, target_pace = templates[wd]
            if plan_date == race_date:
                session_type = "race"
                planned_km = 21.1
                description = "比赛日：半马，前半程保守，后半程逐步加速"
                target_pace = paces["race"]
                race_added = True

            db.add(
                TrainingPlanItem(
                    plan_date=plan_date,
                    weekday=weekday_name,
                    session_type=session_type,
                    description=description,
                    planned_distance_km=planned_km,
                    target_pace_min_per_km=target_pace,
                    status="planned",
                )
            )
            inserted += 1

    if not race_added:
        db.add(
            TrainingPlanItem(
                plan_date=race_date,
                weekday=race_date.strftime("%A"),
                session_type="race",
                description="比赛日：半马，前半程保守，后半程逐步加速",
                planned_distance_km=21.1,
                target_pace_min_per_km=paces["race"],
                status="planned",
            )
        )
        inserted += 1

    db.commit()
    return inserted
