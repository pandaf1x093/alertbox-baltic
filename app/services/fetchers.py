import os, re
from datetime import datetime, timezone
import feedparser

from typing import List, Dict, Any

# --- Триггеры «военка/угрозы» (ru+en), без мусора ---
TRIGGERS = [
    r"\b(мобилиз\w+|резерв\w+|сборы\s*резервист\w+)\b",
    r"\b(учени\w+|маневр\w+|переброс\w+|расквартир\w+)\b",
    r"\b(ПВО|ПРО|зенит\w+|Patriot|Искандер|С-300|С-400)\b",
    r"\b(ракет\w+|баллистическ\w+|артилл\w+|обстрел\w+|залп\w+|пуск\w+)\b",
    r"\b(БПЛА|дрон\w+|беспилот\w+|FPV|UAV|loitering)\b",
    r"\b(эскалац\w+|провокац\w+|нарушен\w+\s*границ\w+|пригранич\w+)\b",
    r"\b(кибератак\w+|DDoS|киберугроз\w+|кибербезопасн\w+)\b",
    r"\b(NATO|НАТО|Article\s*4|статья\s*4)\b",
    r"\b(missile\w*|ballistic|artiller\w*|incursion\w*|troop\s*(build[-\s]?up|movement))\b",
]
PAT = re.compile("|".join(TRIGGERS), re.IGNORECASE)

def is_relevant(title: str, desc: str = "") -> bool:
    text = f"{title or ''} {desc or ''}"
    return bool(PAT.search(text))

def feed_time(entry) -> datetime:
    for k in ("published_parsed","updated_parsed"):
        t = getattr(entry, k, None)
        if t: return datetime(*t[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)

# --- X/Twitter и Telegram в RSS (Nitter/RSSHub) ---
RSSHUB_BASE = os.getenv("RSSHUB_BASE", "https://rsshub.app")
def _rss_for_source(src_type: str, url_or_handle: str) -> str:
    t = (src_type or "rss").lower().strip()
    s = url_or_handle.strip()
    if t == "rss": return s
    if t in ("x","twitter"):
        handle = s
        if s.startswith("http"):
            for mark in ("/twitter.com/","/x.com/","://twitter.com/","://x.com/"):
                if mark in s: handle = s.split(mark,1)[1]; break
        handle = handle.lstrip("@").split("/")[0]
        return f"https://nitter.net/{handle}/rss"
    if t == "telegram":
        ch = s.split("t.me/")[-1].split("/")[0].lstrip("@")
        return f"{RSSHUB_BASE}/telegram/channel/{ch}"
    return s

async def fetch_rss(url: str) -> List[Dict[str, Any]]:
    feed = feedparser.parse(url)
    items = []
    for e in getattr(feed, "entries", []):
        title = getattr(e, "title", "") or ""
        link = getattr(e, "link", "") or ""
        summary = getattr(e, "summary", "") or getattr(e, "description", "") or ""
        score = 2 if is_relevant(title, summary) else 0
        items.append({
            "title": title,
            "url": link,
            "published_at": feed_time(e),
            "raw": {"summary": summary, "score": score},
            "score": score,
        })
    return items

# --- YouTube + транскрипты для Швеца ---
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None

def _youtube_feed_url(channel_or_url: str) -> str:
    s = channel_or_url.strip()
    if s.startswith("UC"):
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={s}"
    if s.startswith("http"):
        if "/channel/" in s:
            ch = s.split("/channel/")[1].split("/")[0]
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={ch}"
        return s
    if s.startswith("@"):
        return f"https://www.youtube.com/{s}"
    return s

def _yt_video_id(url: str) -> str:
    # стандартные формы: watch?v=, shorts/, youtu.be/
    if "watch?v=" in url: return url.split("watch?v=")[1].split("&")[0]
    if "/shorts/" in url: return url.split("/shorts/")[1].split("?")[0]
    if "youtu.be/" in url: return url.split("youtu.be/")[1].split("?")[0]
    return ""

def _pull_transcript(video_url: str) -> str:
    if not YouTubeTranscriptApi: return ""
    vid = _yt_video_id(video_url)
    if not vid: return ""
    try:
        segs = YouTubeTranscriptApi.get_transcript(vid, languages=['ru','uk','en'])
        text = " ".join(s.get("text","") for s in segs if s.get("text"))
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""

async def fetch_youtube(channel_or_url: str, need_transcript: bool = False, max_items: int = 10) -> List[Dict[str, Any]]:
    url = _youtube_feed_url(channel_or_url)
    feed = feedparser.parse(url)
    items = []
    for e in getattr(feed, "entries", [])[:max_items]:
        title = getattr(e, "title", "") or ""
        link = getattr(e, "link", "") or ""
        desc = getattr(e, "summary", "") or ""
        score = 2 if is_relevant(title, desc) else 0
        raw = {"summary": desc, "score": score}
        if need_transcript:
            tr = _pull_transcript(link)
            if tr: raw["transcript"] = tr[:15000]  # безопасный предел
        items.append({
            "title": title,
            "url": link,
            "published_at": feed_time(e),
            "raw": raw,
            "score": score,
        })
    return items

async def fetch_any(src_type: str, url_or_handle: str, *, shvets: bool = False):
    t = (src_type or "rss").lower()
    if t == "youtube":
        return await fetch_youtube(url_or_handle, need_transcript=shvets, max_items=10)
    return await fetch_rss(_rss_for_source(t, url_or_handle))
