import asyncio, random
import httpx
from ..config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

async def _post_json(url: str, headers: dict, payload: dict, retries: int = 5):
    backoff = 1.0
    last_exc = None
    async with httpx.AsyncClient(timeout=90) as client:
        for attempt in range(1, retries + 1):
            r = await client.post(url, headers=headers, json=payload)
            if r.status_code < 400:
                return r.json()
            # 429/5xx — подождём и попробуем снова
            if r.status_code in (429, 500, 502, 503, 504):
                ra = r.headers.get("retry-after")
                if ra and ra.isdigit():
                    sleep_for = float(ra)
                else:
                    jitter = random.uniform(0, 0.5)
                    sleep_for = min(backoff, 10.0) + jitter
                await asyncio.sleep(sleep_for)
                backoff = min(backoff * 2, 10.0)
                last_exc = httpx.HTTPStatusError(f"{r.status_code} {r.reason_phrase}", request=r.request, response=r)
                continue
            r.raise_for_status()
        if last_exc:
            raise last_exc

async def chat(prompt: str, model_groq: str = "mixtral-8x7b-32768"):
    # Пытаемся Groq (если есть ключ)
    if settings.groq_api_key:
        payload = {
            "model": model_groq,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": settings.max_tokens,
        }
        try:
            data = await _post_json(
                GROQ_URL,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                payload=payload,
                retries=3,
            )
            return data["choices"][0]["message"]["content"]
        except Exception:
            pass  # fallback на OpenAI

    # OpenAI (основной или фолбэк)
    if settings.openai_api_key:
        payload = {
            "model": settings.openai_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": settings.max_tokens,
        }
        data = await _post_json(
            OPENAI_URL,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            payload=payload,
            retries=5,
        )
        return data["choices"][0]["message"]["content"]

    raise RuntimeError("No LLM keys configured: set GROQ_API_KEY or OPENAI_API_KEY")
