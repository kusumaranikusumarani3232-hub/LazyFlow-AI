import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    BACKBOARD_API_KEY: str = ""
    BACKBOARD_BASE_URL: str = "https://app.backboard.io/api"
    BACKBOARD_DEFAULT_PROVIDER: str = "openrouter"
    BACKBOARD_DEFAULT_MODEL: str = "meta-llama/llama-3.1-8b-instruct"
    
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
    MAX_FILE_SIZE_MB: int = 50
    MAX_BATCH_FILES: int = 30
    SESSION_EXPIRY_MINUTES: int = 60
    
    # Storage directory for temporary uploads during session
    TEMP_DIR: str = str(BASE_DIR / "temp_storage")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

settings = Settings()
