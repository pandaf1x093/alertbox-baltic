from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime, timedelta
import re

# ---- классификаторы сигналов (темы) ----
KEY_BUCKETS = [
    ("airspace",  r"\b(air\s*space|воздушн\w+\s*пространств\w+|нарушен\w+\s*границ\w+|AWACS|ПВО|SAM|IADS|Patriot|С-300|С-400)\b"),
    ("missiles",  r"\b(missile\w*|ракет\w+|баллистическ\w+|залп\w+|пуск\w+)\b"),
    ("uav",       r"\b(drone\w*|UAV|БПЛА|беспилот\w+|FPV|loitering)\b"),
    ("maneuver",  r"\b(учени\w+|маневр\w+|переброс\w+|передислокац\w+|концентраци\w+\s*войск)\b"),
    ("border",    r"\b(incursion\w*|пригранич\w+|нарушен\w+\s*границ\w+)\b"),
    ("cyber",     r"\b(кибератак\w+|DDoS|cyber\s*attack\w*|киберугроз\w+)\b"),
    ("diplo",     r"\b(санкц\w+|дипломат\w+|посольств\w+|консульств\w+|эвакуац\w+\s*персонал\w*)\b"),
]
KEY_PATS = [(k, re.compile(rx, re.IGNORECASE)) for k, rx in KEY_BUCKETS]

@dataclass
class Sig:
    t: datetime
    title: str
    url: str
    org: str
    country: str
    bucket: str
    weight: int

def bucket_of(title: str, text: str) -> str | None:
    s = f"{title or ''} {text or ''}"
    for k, pat in KEY_PATS:
        if pat.search(s):
            return k
    return None

def summarize_trends(signals: List[Sig], now: datetime, days: int = 14) -> str:
    """
    Возвращает короткий служебный текст с динамикой по темам за N дней.
    Это скрытый контекст — НЕ выводим в отчёт.
    """
    since = now - timedelta(days=days)
    sigs = [s for s in signals if s.t >= since]
    if not sigs:
        return "NoLocalTrends: insufficient recent signals."
    by_bucket: Dict[str, List[Sig]] = {}
    for s in sigs:
        by_bucket.setdefault(s.bucket, []).append(s)

    lines = []
    for b, arr in by_bucket.items():
        arr = sorted(arr, key=lambda x: x.t)
        n = len(arr)
        if n < 3:
            trend = "unstable"
        else:
            xs = [i/(n-1) for i in range(n)]
            ys = [s.weight for s in arr]
            xbar = sum(xs)/n; ybar = sum(ys)/n
            cov = sum((x-xbar)*(y-ybar) for x,y in zip(xs,ys))
            var = sum((x-xbar)**2 for x in xs) or 1e-9
            slope = cov/var
            trend = "rising" if slope > 0.1 else ("falling" if slope < -0.1 else "flat")
        cc: Dict[str,int] = {}
        for s in arr:
            cc[s.country] = cc.get(s.country,0)+1
        top_cc = ", ".join(sorted(cc, key=cc.get, reverse=True)[:3]) or "-"
        lines.append(f"{b}: {trend}; top-countries: {top_cc}; count={len(arr)}")
    return "LocalTrends:\n" + "\n".join(sorted(lines))
