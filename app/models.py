from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from .db import Base

class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    url: Mapped[str] = mapped_column(String(500), unique=True)
    type: Mapped[str] = mapped_column(String(50), default="rss")   # rss | youtube | html
    country: Mapped[str] = mapped_column(String(32), default="")   # EE/LV/LT/FI/PL/UA/EU/NATO/...
    org: Mapped[str] = mapped_column(String(64), default="")       # MOD/MFA/MEDIA/NATO/COUNCIL/EU
    priority: Mapped[int] = mapped_column(Integer, default=5)      # 1..10

class NewsItem(Base):
    __tablename__ = "news_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(1000))
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    lang: Mapped[str] = mapped_column(String(8), default="ru")
    raw: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("url", name="uq_news_url"),)
    source = relationship("Source")

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    period: Mapped[str] = mapped_column(String(64), default="daily")
    region: Mapped[str] = mapped_column(String(64), default="Baltics")
    lang: Mapped[str] = mapped_column(String(8), default="ru")
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default={})
