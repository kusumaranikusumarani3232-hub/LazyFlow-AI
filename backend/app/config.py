import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    BACKBOARD_API_KEY: str = ""
    BACKBOARD_BASE_URL: str = "https://app.backboard.io/api"
    BACKBOARD_DEFAULT_PROVIDER: str = "openrouter"
    BACKBOARD_DEFAULT_MODEL: str = "meta-llama/llama-3.1-8b-instruct"
    
    CORS_ORIGINS: str = (
        "https://lazy-flow-ai.vercel.app,https://lazyflow-ai.vercel.app,"
        "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    )
    # Allows all Vercel deployments (production, previews, branch deployments)
    CORS_ORIGIN_REGEX: str = r"^https:\/\/([a-zA-Z0-9_-]+\.)*vercel\.app$"
    MAX_FILE_SIZE_MB: int = 50
    MAX_BATCH_FILES: int = 30
    SESSION_EXPIRY_MINUTES: int = 60
    
    # Storage directory for temporary uploads during session
    TEMP_DIR: str = str(BASE_DIR / "temp_storage")

    # OCR configuration
    TESSERACT_CMD: Optional[str] = None
    OCR_ENABLED: bool = True
    OCR_MAX_PAGES: int = 2
    OCR_MAX_IMAGE_DIMENSION: int = 2000
    OCR_TIMEOUT_SECONDS: int = 10

    # Vision Classification configuration
    VISION_ENABLED: bool = True
    VISION_CONFIDENCE_THRESHOLD: float = 0.18
    VISION_MAX_INPUT_DIMENSION: int = 512

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        # Always permit the verified production Vercel frontend domains and local dev servers
        default_origins = [
            "https://lazy-flow-ai.vercel.app",
            "https://lazyflow-ai.vercel.app",
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ]
        origins = list(default_origins)

        if self.CORS_ORIGINS:
            raw = self.CORS_ORIGINS.strip()
            # Support JSON array format e.g. ["https://..."] as well as comma-separated
            items: List[str] = []
            if raw.startswith("[") and raw.endswith("]"):
                try:
                    import json
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        items = [str(x) for x in parsed]
                except Exception:
                    items = raw.strip("[]").split(",")
            else:
                items = raw.split(",")

            for item in items:
                cleaned = item.strip().strip("'\"").rstrip("/")
                if cleaned and cleaned not in origins:
                    origins.append(cleaned)
        return origins

settings = Settings()
