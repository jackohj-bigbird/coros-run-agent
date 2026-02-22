from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.models import TrainingPlanItem
from app.services.planner import generate_half_marathon_plan


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_generate_plan_has_race_day() -> None:
    db = _session()
    inserted = generate_half_marathon_plan(
        db=db,
        start_date=date(2026, 2, 22),
        race_date=date(2026, 5, 1),
        target_hm_time_min=100.0,
    )
    assert inserted > 0

    race_item = db.scalar(select(TrainingPlanItem).where(TrainingPlanItem.plan_date == date(2026, 5, 1)))
    assert race_item is not None
    assert race_item.session_type == "race"
    assert race_item.planned_distance_km == 21.1
