import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import Activity

STRAVA_OAUTH_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
STRAVA_ACTIVITY_DETAIL_URL = "https://www.strava.com/api/v3/activities/{activity_id}"
STRAVA_WEBHOOK_SUBSCRIPTION_URL = "https://www.strava.com/api/v3/push_subscriptions"


class StravaService:
    def __init__(self) -> None:
        self.client_id = settings.strava_client_id
        self.client_secret = settings.strava_client_secret
        self.refresh_token = settings.strava_refresh_token
        self._activity_id_bigint_checked = False

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def refresh_access_token(self) -> str:
        if not self.is_configured():
            raise ValueError("Strava credentials are missing. Please fill .env.")

        response = requests.post(
            STRAVA_OAUTH_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["access_token"]

    def fetch_recent_activities(self, after_epoch: Optional[int] = None, per_page: int = 100) -> List[Dict[str, Any]]:
        token = self.refresh_access_token()
        params: dict[str, Any] = {"page": 1, "per_page": per_page}
        if after_epoch:
            params["after"] = after_epoch

        response = requests.get(
            STRAVA_ACTIVITIES_URL,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def fetch_activity_by_id(self, activity_id: int) -> Dict[str, Any]:
        token = self.refresh_access_token()
        response = requests.get(
            STRAVA_ACTIVITY_DETAIL_URL.format(activity_id=activity_id),
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def create_webhook_subscription(self, callback_url: str, verify_token: str) -> Dict[str, Any]:
        response = requests.post(
            STRAVA_WEBHOOK_SUBSCRIPTION_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "callback_url": callback_url,
                "verify_token": verify_token,
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def list_webhook_subscriptions(self) -> List[Dict[str, Any]]:
        response = requests.get(
            STRAVA_WEBHOOK_SUBSCRIPTION_URL,
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def delete_webhook_subscription(self, subscription_id: int) -> Dict[str, Any]:
        response = requests.delete(
            f"{STRAVA_WEBHOOK_SUBSCRIPTION_URL}/{subscription_id}",
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=20,
        )
        response.raise_for_status()
        return {"deleted_id": subscription_id}

    def upsert_run_activities(self, db: Session, activities: list[dict[str, Any]]) -> int:
        self._ensure_activity_id_bigint(db)
        inserted = 0
        for item in activities:
            if item.get("type") != "Run":
                continue

            activity_id = item["id"]
            exists = db.scalar(select(Activity).where(Activity.strava_activity_id == activity_id))
            if exists:
                continue

            start_date = datetime.fromisoformat(item["start_date"].replace("Z", "+00:00")).astimezone(timezone.utc)
            record = Activity(
                strava_activity_id=activity_id,
                name=item.get("name", "Run"),
                activity_type=item.get("type", "Run"),
                start_date=start_date,
                distance_m=float(item.get("distance", 0)),
                moving_time_s=int(item.get("moving_time", 0)),
                elapsed_time_s=int(item.get("elapsed_time", 0)),
                total_elevation_gain_m=float(item.get("total_elevation_gain", 0)),
                average_heartrate=item.get("average_heartrate"),
                max_heartrate=item.get("max_heartrate"),
                average_speed_mps=item.get("average_speed"),
                raw_json=json.dumps(item, ensure_ascii=False),
            )
            db.add(record)
            inserted += 1

        if inserted:
            db.commit()
        return inserted

    def _ensure_activity_id_bigint(self, db: Session) -> None:
        if self._activity_id_bigint_checked:
            return

        bind = db.get_bind()
        if not bind.dialect.name.startswith("postgresql"):
            self._activity_id_bigint_checked = True
            return

        with bind.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS activities "
                    "ALTER COLUMN strava_activity_id TYPE BIGINT "
                    "USING strava_activity_id::BIGINT"
                )
            )
        self._activity_id_bigint_checked = True
