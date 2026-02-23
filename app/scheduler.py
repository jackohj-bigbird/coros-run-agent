from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.models import Activity, ReminderLog, TrainingPlanItem
from app.services.analysis import build_weekly_summary, format_pace
from app.services.reminder import EmailReminderService
from app.services.strava import StravaService


class SchedulerService:
    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler(timezone=settings.timezone)
        self.strava = StravaService()
        self.mailer = EmailReminderService()

    def start(self) -> None:
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            # Avoid crashing whole API startup on transient DB/network issues.
            return

        # Daily sync at 06:10 local time.
        self.scheduler.add_job(self.sync_activities_job, "cron", hour=6, minute=10, id="sync_activities")
        # Reminder every day, internal logic only sends on planned run days.
        self.scheduler.add_job(
            self.run_day_reminder_job,
            "cron",
            hour=settings.default_reminder_hour,
            minute=settings.default_reminder_minute,
            id="run_day_reminder",
        )
        # Weekly summary on Sunday 20:30.
        self.scheduler.add_job(self.weekly_summary_job, "cron", day_of_week="sun", hour=20, minute=30, id="weekly_summary")
        self.scheduler.start()

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def sync_activities_job(self) -> None:
        with SessionLocal() as db:
            if not self.strava.is_configured():
                return

            last_activity = db.scalar(select(Activity).order_by(Activity.start_date.desc()).limit(1))
            # Sync recent 30 days if no checkpoint.
            after_epoch = None
            if last_activity:
                dt = last_activity.start_date - timedelta(days=30)
                after_epoch = int(dt.timestamp())

            activities = self.strava.fetch_recent_activities(after_epoch=after_epoch)
            self.strava.upsert_run_activities(db, activities)

    def run_day_reminder_job(self) -> None:
        with SessionLocal() as db:
            today = datetime.now(ZoneInfo(settings.timezone)).date()
            item = db.scalar(select(TrainingPlanItem).where(TrainingPlanItem.plan_date == today))
            if not item:
                return
            if not self.mailer.is_configured():
                return

            subject = f"[跑步提醒] {today} {item.session_type} {item.planned_distance_km}km"
            body = (
                f"今天是训练日（{item.weekday}）\n"
                f"训练类型: {item.session_type}\n"
                f"计划距离: {item.planned_distance_km} km\n"
                f"目标配速: {item.target_pace_min_per_km}\n"
                f"说明: {item.description}\n\n"
                "完成后记得同步手表数据到 COROS/Strava。"
            )
            self.mailer.send_email(subject, body)
            db.add(
                ReminderLog(
                    reminder_type="run_day",
                    target_date=today,
                    channel="email",
                    subject=subject,
                    body=body,
                )
            )
            db.commit()

    def weekly_summary_job(self) -> None:
        with SessionLocal() as db:
            if not self.mailer.is_configured():
                return
            summary = build_weekly_summary(db, anchor=date.today())
            subject = f"[周跑步总结] {summary.week_start} - {summary.week_end}"
            body = (
                f"本周跑步次数: {summary.run_count}\n"
                f"总里程: {summary.total_distance_km} km\n"
                f"总时长: {summary.total_time_min} min\n"
                f"平均配速: {format_pace(summary.avg_pace_min_per_km)}\n"
                f"最长一次: {summary.longest_run_km} km\n"
                f"计划完成率: {int(summary.completion_rate * 100)}%\n"
            )
            self.mailer.send_email(subject, body)
            db.add(
                ReminderLog(
                    reminder_type="weekly_summary",
                    target_date=date.today(),
                    channel="email",
                    subject=subject,
                    body=body,
                )
            )
            db.commit()
