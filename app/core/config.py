from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ✅ Database
    database_url: str = Field(..., alias="DATABASE_URL")

    # ✅ Cloudinary
    cloudinary_cloud_name: str = Field(..., alias="CLOUDINARY_CLOUD_NAME")
    cloudinary_api_key: str = Field(..., alias="CLOUDINARY_API_KEY")
    cloudinary_api_secret: str = Field(..., alias="CLOUDINARY_API_SECRET")

    stripe_secret_key: str = Field(..., alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field(..., alias="STRIPE_WEBHOOK_SECRET")

    # Password reset and SMTP email
    password_reset_base_url: str = Field(
        "http://your-app/reset-password",
        alias="PASSWORD_RESET_BASE_URL"
    )
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    smtp_from_email: str | None = Field(default=None, alias="SMTP_FROM_EMAIL")

    class Config:
        env_file = ".env"
        extra = "allow"  # Ignore extra env vars


settings = Settings()
