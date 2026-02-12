from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ✅ Database
    database_url: str = Field(..., alias="DATABASE_URL")

    # ✅ Cloudinary
    cloudinary_cloud_name: str = Field(..., alias="CLOUDINARY_CLOUD_NAME")
    cloudinary_api_key: str = Field(..., alias="CLOUDINARY_API_KEY")
    cloudinary_api_secret: str = Field(..., alias="CLOUDINARY_API_SECRET")

    class Config:
        env_file = ".env"
        extra = "forbid"


settings = Settings()
