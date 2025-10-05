import os, math, asyncio
import httpx

BOT = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

API = f"https://api.telegram.org/bot{BOT}/sendMessage"

def _chunks(s: str, n: int = 3500):
    for i in range(0, len(s), n):
        yield s[i:i+n]

async def send_telegram(text: str, *, parse_mode: str = "HTML"):
    if not BOT or not CHAT_ID:
        return {"ok": False, "reason": "No telegram creds"}
    async with httpx.AsyncClient(timeout=20) as cli:
        resps = []
        for part in _chunks(text, 3500):  # телега лимит ~4096
            r = await cli.post(API, data={
                "chat_id": CHAT_ID,
                "text": part,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            })
            resps.append(r.status_code)
            if r.status_code >= 400:
                break
        return {"ok": all(code < 400 for code in resps), "parts": len(resps)}
