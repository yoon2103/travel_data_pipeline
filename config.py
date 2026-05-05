import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Required env var '{key}' is not set. Check your .env file.")
    return val


def _optional(key: str) -> str | None:
    return os.getenv(key) or None


# TourAPI
TOURAPI_SERVICE_KEY: str = _require("TOURAPI_SERVICE_KEY")
TOURAPI_BASE_URL: str = "https://apis.data.go.kr/B551011/KorService2"

# OpenAI (optional — skip embedding if not set)
OPENAI_API_KEY: str | None = _optional("OPENAI_API_KEY")
OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

# Anthropic (optional — skip AI tagging if not set)
ANTHROPIC_API_KEY: str | None = _optional("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"

# Naver Local Search API (optional — enrichment_service 전용)
NAVER_CLIENT_ID: str | None = _optional("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET: str | None = _optional("NAVER_CLIENT_SECRET")

# Kakao REST API (optional — enrichment_service 전용)
KAKAO_REST_API_KEY: str | None = _optional("KAKAO_REST_API_KEY")

# PostgreSQL
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
DB_NAME: str = _require("DB_NAME")
DB_USER: str = _require("DB_USER")
DB_PASSWORD: str = _require("DB_PASSWORD")
