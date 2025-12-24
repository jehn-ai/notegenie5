import os
import asyncio
import random
import time
from functools import partial
from fastapi import HTTPException
from google import genai
from google.genai import types

# =========================
# Gemini Configuration
MODEL_NAME = "gemini-2.0-flash-lite-001"

MAX_RETRIES = 4
BASE_BACKOFF = 0.8
MAX_BACKOFF = 8.0
RPM = 10             # safe under 15 RPM free-tier
TPM = 1_000_000      # tokens per minute free-tier
RPD = 1_500          # requests per day free-tier
QUEUE_SIZE = 50      # max concurrent chunks in queue

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not found in environment")

client = genai.Client(api_key=GEMINI_API_KEY)

# =========================
# Structured Output Schema
SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["summary"]
}

# =========================
# Async-safe token bucket for RPM
class RateLimiter:
    def __init__(self, rpm: int):
        self._max_tokens = rpm
        self._semaphore = asyncio.Semaphore(rpm)
        self._interval = 60  # seconds
        self._last_refill = asyncio.get_event_loop().time()
        asyncio.create_task(self._refill_loop())

    async def acquire(self):
        await self._semaphore.acquire()

    async def _refill_loop(self):
        while True:
            await asyncio.sleep(1)
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_refill
            if elapsed >= self._interval:
                refill = self._max_tokens - self._semaphore._value
                for _ in range(refill):
                    self._semaphore.release()
                self._last_refill = now

rate_limiter = RateLimiter(RPM)

# =========================
# Async-safe queue for chunk processing
class GeminiQueue:
    def __init__(self):
        self._queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        asyncio.create_task(self._worker())

    async def submit(self, coro):
        future = asyncio.get_event_loop().create_future()
        await self._queue.put((coro, future))
        return await future

    async def _worker(self):
        while True:
            coro, future = await self._queue.get()
            try:
                result = await coro()
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            finally:
                self._queue.task_done()

gemini_queue = GeminiQueue()

# =========================
# Token and Daily Request Tracker
class GeminiQuota:
    def __init__(self):
        self.tokens_this_minute = 0
        self.minute_start = time.time()
        self.requests_today = 0
        self.day_start = time.time()

    async def check_and_wait(self, estimated_tokens: int):
        now = time.time()
        # reset per-minute token count
        if now - self.minute_start >= 60:
            self.tokens_this_minute = 0
            self.minute_start = now
        # reset daily request count
        if now - self.day_start >= 86400:
            self.requests_today = 0
            self.day_start = now

        # TPM enforcement
        while self.tokens_this_minute + estimated_tokens > TPM:
            await asyncio.sleep(1)
            now = time.time()
            if now - self.minute_start >= 60:
                self.tokens_this_minute = 0
                self.minute_start = now

        # RPD enforcement
        if self.requests_today >= RPD:
            raise HTTPException(
                status_code=429,
                detail="Daily Gemini request quota reached. Try again tomorrow."
            )

        # reserve quota
        self.tokens_this_minute += estimated_tokens
        self.requests_today += 1

quota_tracker = GeminiQuota()

# =========================
# Internal blocking SDK call
def _sync_generate(prompt: str):
    return client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=SUMMARY_SCHEMA,
        ),
    )

# =========================
# Async retry wrapper with adaptive backoff
async def _retry(fn, max_retries=MAX_RETRIES):
    for attempt in range(1, max_retries + 1):
        try:
            return await fn()
        except Exception as e:
            status = getattr(e, "status_code", None) or getattr(e, "code", None)

            if status == 429:
                if attempt == max_retries:
                    raise HTTPException(
                        status_code=429,
                        detail="Gemini quota exceeded. Try again later."
                    )
                # adaptive backoff: exponential + jitter
                delay = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)
                continue

            if status in (400, 403):
                raise HTTPException(
                    status_code=400,
                    detail="Gemini rejected the request (payload or API key)"
                )

            if status == 413:
                raise HTTPException(
                    status_code=413,
                    detail="Input too large for Gemini Flash-Lite"
                )

            if status and status >= 500:
                raise HTTPException(
                    status_code=502,
                    detail="Gemini service temporarily unavailable"
                )

            raise HTTPException(
                status_code=502,
                detail=f"Unexpected Gemini SDK error: {str(e)}"
            )

# =========================
# Full async-safe Gemini call with TPM, RPD, RPM, queue, retries
async def call_gemini(prompt: str, estimated_tokens: int = 1000) -> dict:
    """
    estimated_tokens: rough number of tokens for the prompt
    """

    if not prompt or not prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="Empty prompt sent to Gemini"
        )

    # enforce TPM and RPD quotas before sending
    await quota_tracker.check_and_wait(estimated_tokens)

    async def _gemini_job():
        await rate_limiter.acquire()  # RPM-safe
        loop = asyncio.get_running_loop()
        response = await _retry(lambda: loop.run_in_executor(None, partial(_sync_generate, prompt)))
        if not response or not response.parsed:
            raise HTTPException(
                status_code=502,
                detail="Gemini returned invalid structured output"
            )
        return response.parsed

    return await gemini_queue.submit(_gemini_job)
