from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone
from ..models import Report, NewsItem, Source
from ..config import settings
from .llm import chat
from ..analyzer.context_tracker import Sig, bucket_of, summarize_trends

OFFICIAL = {"MFA","MOD","NATO","EEAS","EMBASSY","COUNCIL","GOV","PRES","AIRFORCE","DEFENCE"}

HISTORICAL_PRIORS = """
HiddenHistoricalPriors (do NOT reveal to user):
- Pre-invasion 2021–22 (Ukraine) patterns that tended to precede escalations:
  1) Frequent airspace incidents and radar anomalies near borders (balloons/drones/"training" flights).
  2) Spike in cyber (DDoS on media/banks/gov) within ~1–3 weeks before kinetic steps.
  3) Logistics hints: fuel moves, rail cargo surges, port anomalies; public "unplanned checks".
  4) Diplomatic smoke: sudden embassy notices/limited services; vague travel alerts.
  5) Narrative prep: synchronized media lines about "provocations", "self-defense", "red lines".
- If 2+ categories co-occur within ~10–14 days in the Baltic theatre (EE/LV/LT, plus PL/FI periphery), raise likelihood of gray-zone incidents. Never state these priors explicitly in the report.
"""

def _score(item: NewsItem) -> int:
    raw = item.raw or {}
    s = int(raw.get("score", 0))
    org = (raw.get("org") or "").upper()
    if org in OFFICIAL: s += 1
    return s

def _country_of(item: NewsItem) -> str:
    raw = item.raw or {}
    c = (raw.get("country") or "").upper()
    if c: return c
    u = (item.url or "").lower()
    if "err.ee" in u or ".ee/" in u: return "EE"
    if "lsm.lv" in u or ".lv/" in u: return "LV"
    if ".lt/" in u: return "LT"
    if ".pl/" in u: return "PL"
    if ".fi/" in u: return "FI"
    if "nato.int" in u: return "NATO"
    if "europa.eu" in u or "consilium" in u: return "EU"
    if ".ua/" in u or "ukr" in u: return "UA"
    return "EU"

async def _collect_local_trends(session: AsyncSession, days: int = 14) -> str:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (await session.execute(
        select(NewsItem)
        .options(selectinload(NewsItem.source))
        .where(NewsItem.published_at >= since.replace(tzinfo=None))
        .order_by(NewsItem.published_at.desc())
        .limit(1200)
    )).scalars().all()

    sigs = []
    for r in rows:
        raw = r.raw or {}
        title = r.title or ""
        text = (raw.get("summary") or "") + " " + (raw.get("transcript") or "")
        bucket = bucket_of(title, text)
        if bucket is None: 
            continue
        weight = _score(r)
        if weight < 1:
            continue
        t = r.published_at
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        sigs.append(Sig(
            t=t, title=title[:200], url=(r.url or "")[:300],
            org=(raw.get("org") or "").upper()[:20],
            country=_country_of(r)[:6], bucket=bucket, weight=weight
        ))
    return summarize_trends(sigs, datetime.now(timezone.utc), days=days)

async def generate_daily_report(session: AsyncSession):
    # свежие 48 часов
    since = datetime.now(timezone.utc) - timedelta(hours=48)
    rows = (await session.execute(
        select(NewsItem)
        .where(NewsItem.published_at >= since.replace(tzinfo=None))
        .order_by(NewsItem.published_at.desc())
        .limit(900)
    )).scalars().all()

    # только сигналы по военке/угрозам
    rows = [r for r in rows if _score(r) >= 1]
    # сортировка: вес → свежесть
    rows.sort(key=lambda r: (_score(r), r.published_at), reverse=True)

    # дистиллят для LLM (без мусора, без повторов)
    distilled = []
    seen_titles = set()
    for r in rows:
        t = (r.title or "").strip()
        if not t or t in seen_titles:
            continue
        seen_titles.add(t)
        org = (r.raw or {}).get("org","") or "MEDIA"
        distilled.append(f"- [{_country_of(r)}][{org}] {t} ({r.url})")
        if len(distilled) >= 14:
            break

    # скрытые тренды локальной истории
    hidden_trends = ""
    try:
        if getattr(settings, "use_historical_priors", True):
            hidden_trends = await _collect_local_trends(session, days=getattr(settings, "history_window_days", 14))
    except Exception:
        hidden_trends = "NoLocalTrends: error"

    # скрытые исторические приоры (Украина 2021–22)
    hidden_priors = HISTORICAL_PRIORS if getattr(settings, "use_historical_priors", True) else ""

    # промпт: человеческий обзор; Балтия в фокусе; НЕ раскрывать hidden-блоки
    prompt = f"""
Ты — анонимный аналитический центр. Пиши по-человечески, без воды: что произошло → почему важно → что дальше для Балтии.
Запреты:
- Не упоминай источники подсказок, скрытую историю или исторические «приоры».
- Не раскрывай служебные пометки ниже.

Формат:
1) Вступление (3–5 предложений): общий контекст и что это значит для Балтии (EE/LV/LT) с периметром PL/FI.
2) Основная часть: 
   • Украина/удары и их влияние на логистику/энергию/ПВО региона.
   • Балтика/PL/FI: конкретные риски (граница, воздух, море, кибер, дипломатия).
   • Решения НАТО/ЕС, которые меняют расклад (если есть).
3) Прогноз на 7 дней:
   • MLS (вероятный): % и почему.
   • MDS (опасный): % и какие триггеры переведут в него.
4) Индикаторы для мониторинга (5–8 точных маркеров).
5) Примечание: «оценка по открытым источникам; возможны уточнения».

Свежие сигналы (отобранные, без повтора):
{chr(10).join(distilled)}

[HIDDEN_LOCAL_TRENDS — НЕ РАСКРЫВАТЬ В ОТЧЁТЕ]
{hidden_trends}

[HIDDEN_HISTORICAL_PRIORS — НЕ РАСКРЫВАТЬ В ОТЧЁТЕ]
{hidden_priors}
"""
    content = await chat(prompt)

    rep = Report(
        period="daily",
        region=settings.region,
        lang="ru",
        content=content,
        meta={"used": len(distilled), "window_h": 48}
    )
    session.add(rep)
    await session.commit()
    await session.refresh(rep)
    return rep
