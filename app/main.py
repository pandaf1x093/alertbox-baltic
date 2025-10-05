from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from zoneinfo import ZoneInfo

from .db import get_session, engine, Base
from .models import Report, Source, NewsItem
from .schemas import ReportOut
from .config import settings
from .services.reports import generate_daily_report
from .services.fetchers import fetch_any, is_relevant
from .services.notify import send_telegram

app = FastAPI(title="AlertBox Baltic API")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/health")
async def health():
    return {"status": "ok", "region": settings.region}

@app.post("/report", response_model=ReportOut)
async def make_report(session: AsyncSession = Depends(get_session)):
    try:
        rep = await generate_daily_report(session)
        return rep
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/reports", response_model=list[ReportOut])
async def list_reports(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Report).order_by(Report.created_at.desc()).limit(20))).scalars().all()
    return rows

@app.get("/sources")
async def list_sources(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Source))).scalars().all()
    rows = sorted(rows, key=lambda r: getattr(r, "priority", 0), reverse=True)
    return [
        {"id": r.id, "name": r.name, "url": r.url, "type": getattr(r, "type","rss"),
         "country": getattr(r,"country",""), "org": getattr(r,"org",""),
         "priority": getattr(r,"priority",0)}
        for r in rows
    ]

@app.post("/ingest/all")
async def ingest_all(session: AsyncSession = Depends(get_session)):
    sources = (await session.execute(select(Source))).scalars().all()
    total_added = 0
    for src in sources:
        is_shvets = "швец" in (src.name or "").lower() or "yuryshvets" in (src.url or "").lower()
        items = await fetch_any(src.type, src.url, shvets=is_shvets)
        for it in items:
            exists = (await session.execute(select(NewsItem).where(NewsItem.url == it["url"]))).scalars().first()
            if exists:
                continue
            pub = it["published_at"]
            if hasattr(pub, "tzinfo") and pub.tzinfo is not None:
                pub = pub.replace(tzinfo=None)
            session.add(NewsItem(
                source_id=src.id, title=(it["title"] or "")[:500], url=(it["url"] or "")[:1000],
                published_at=pub if isinstance(pub, datetime) else datetime.utcnow(),
                lang="ru", raw=it.get("raw", {})
            ))
            total_added += 1
    await session.commit()
    return {"sources": len(sources), "added": total_added}

# ---------- Telegram notifications ----------
@app.post("/notify/test")
async def notify_test():
    ok = await send_telegram("<b>AlertBox test</b> — проверка связи.", parse_mode="HTML")
    if not ok.get("ok"):
        raise HTTPException(status_code=500, detail=str(ok))
    return ok

@app.post("/notify/last")
async def notify_last(session: AsyncSession = Depends(get_session)):
    last = (await session.execute(select(Report).order_by(Report.created_at.desc()).limit(1))).scalars().first()
    if not last:
        raise HTTPException(status_code=404, detail="No report")
    TZ = ZoneInfo("Europe/Tallinn")
    title = f"🛰️ AlertBox Baltic — обзор ({datetime.now(TZ).strftime('%d.%m.%Y %H:%M %Z')})"
    text = f"<b>{title}</b>\n\n{last.content}"
    ok = await send_telegram(text, parse_mode="HTML")
    if not ok.get("ok"):
        raise HTTPException(status_code=500, detail=str(ok))
    return ok
