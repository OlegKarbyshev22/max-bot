import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")

def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.proxyapi.ru/v1").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
LLM_MODEL = os.getenv("LLM_MODEL", "inclusionai/ling-3.0-flash")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "180"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2500"))
LLM_LOCAL_MODE = env_flag("LLM_LOCAL_MODE")
LLM_USE_JSON_SCHEMA = env_flag("LLM_USE_JSON_SCHEMA")

EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", LLM_BASE_URL).rstrip("/")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", LLM_API_KEY)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-4b")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
EMBEDDING_SEND_DIMENSIONS = env_flag("EMBEDDING_SEND_DIMENSIONS", default=True)
EMBEDDING_TIMEOUT = float(os.getenv("EMBEDDING_TIMEOUT", "180"))
ENABLE_VECTOR_SEARCH = env_flag("ENABLE_VECTOR_SEARCH")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "max_courses")
POSTGRES_USER = os.getenv("POSTGRES_USER", "maxbot")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")


def require_database_password() -> str:
    if not POSTGRES_PASSWORD:
        raise RuntimeError("POSTGRES_PASSWORD is not set in .env")
    return POSTGRES_PASSWORD
