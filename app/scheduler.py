import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from .db import engine
from .models import Source, NewsItem
from .services.notify import send_telegram
from .services.fetchers import fetch_any
from .services.reports import generate_daily_report

TZ = ZoneInfo("Europe/Tallinn")
async_session_maker = sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

async def do_ingest(session: AsyncSession) -> int:
    from sqlalchemy import select
    sources = (await session.execute(select(Source))).scalars().all()
    total = 0
    for src in sources:
        is_shvets = "швец" in (src.name or "").lower() or "yuryshvets" in (src.url or "").lower()
        items = await fetch_any(getattr(src, "type", "rss"), src.url, shvets=is_shvets)
        for it in items:
            from sqlalchemy import select as _sel
            exists = (await session.execute(_sel(NewsItem).where(NewsItem.url == it["url"]))).scalars().first()
            if exists:
                continue
            pub = it["published_at"]
            if hasattr(pub, "tzinfo") and pub.tzinfo is not None:
                pub = pub.replace(tzinfo=None)
            session.add(NewsItem(
                source_id=src.id,
                title=(it["title"] or "")[:500],
                url=(it["url"] or "")[:1000],
                published_at=pub if isinstance(pub, datetime) else datetime.utcnow(),
                lang="ru",
                raw=it.get("raw", {})
            ))
            total += 1
    await session.commit()
    return total

async def job_once(tag: str):
    async with async_session_maker() as session:
        added = await do_ingest(session)
        rep = await generate_daily_report(session)
        title = f"🛰️ AlertBox Baltic — обзор ({datetime.now(TZ).strftime('%d.%m.%Y %H:%M %Z')})"
        text = f"<b>{title}</b>\n\n{rep.content}"
        await send_telegram(text)

async def run_scheduler():
    print("[scheduler] Europe/Tallinn cron at 10:00 & 22:00")
    sched = AsyncIOScheduler(timezone=TZ, event_loop=asyncio.get_running_loop())
    sched.add_job(job_once, CronTrigger(hour=10, minute=0, timezone=TZ), kwargs={"tag": "morning"})
    sched.add_job(job_once, CronTrigger(hour=22, minute=0, timezone=TZ), kwargs={"tag": "evening"})
    sched.start()
    for j in sched.get_jobs():
        print("[scheduler] next:", j.trigger, "->", j.next_run_time)
    # держим цикл вечно
    await asyncio.Event().wait()

def main():
    asyncio.run(run_scheduler())

if __name__ == "__main__":
    main()
