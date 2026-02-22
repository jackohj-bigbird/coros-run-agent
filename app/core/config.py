from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="dev", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    timezone: str = Field(default="Asia/Shanghai", alias="TIMEZONE")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    database_url: str = Field(default="sqlite:///./running_agent.db", alias="DATABASE_URL")

    strava_client_id: str = Field(default="", alias="STRAVA_CLIENT_ID")
    strava_client_secret: str = Field(default="", alias="STRAVA_CLIENT_SECRET")
    strava_refresh_token: str = Field(default="", alias="STRAVA_REFRESH_TOKEN")
    strava_athlete_id: str = Field(default="", alias="STRAVA_ATHLETE_ID")
    strava_webhook_verify_token: str = Field(default="", alias="STRAVA_WEBHOOK_VERIFY_TOKEN")
    strava_webhook_callback_url: str = Field(default="", alias="STRAVA_WEBHOOK_CALLBACK_URL")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    smtp_host: str = Field(default="smtp.qq.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=465, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_use_ssl: bool = Field(default=True, alias="SMTP_USE_SSL")
    email_from: str = Field(default="", alias="EMAIL_FROM")
    email_to: str = Field(default="", alias="EMAIL_TO")

    default_reminder_hour: int = Field(default=19, alias="DEFAULT_REMINDER_HOUR")
    default_reminder_minute: int = Field(default=0, alias="DEFAULT_REMINDER_MINUTE")


settings = Settings()
