from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    max_tokens: int = int(os.getenv("MAX_TOKENS", "400"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./alertbox.db")
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    report_langs: list[str] = os.getenv("REPORT_LANGS", "ru,en").split(",")
    schedule_cron: str = os.getenv("SCHEDULE_CRON", "0 6,18 * * *")
    region: str = os.getenv("REGION", "Baltics")
    rss_sources: list[str] = os.getenv("RSS_SOURCES", "").split(",") if os.getenv("RSS_SOURCES") else []

settings = Settings()
