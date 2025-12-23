import asyncio
import time

# Max concurrent Gemini requests
MAX_CONCURRENT_REQUESTS = 2  # SAFE for 15 RPM

gemini_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# Simple RPM guard
LAST_REQUEST_TIME = 0
MIN_INTERVAL = 4  # seconds (15 RPM ≈ 1 request every 4s)

async def rpm_guard():
    global LAST_REQUEST_TIME
    now = time.time()
    elapsed = now - LAST_REQUEST_TIME

    if elapsed < MIN_INTERVAL:
        await asyncio.sleep(MIN_INTERVAL - elapsed)

    LAST_REQUEST_TIME = time.time()
