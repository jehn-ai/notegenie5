import os
import asyncio
import random
from fastapi import HTTPException
from google import genai
from google.genai import types


# Gemini Configuration

MODEL_NAME = "gemini-2.0-flash-lite-001"

MAX_RETRIES = 4
BASE_BACKOFF = 0.8
MAX_BACKOFF = 8.0

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Structured Output Schema

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["summary"]
}

# Core Gemini Call


async def call_gemini(prompt: str):
    if not prompt or not prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="Empty prompt sent to Gemini"
        )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=SUMMARY_SCHEMA,
                ),
            )

            #  Parsed + schema-validated
            return response.parsed

        except Exception as e:
            status = getattr(e, "status_code", None)

            #  Rate limit (retryable)
            if status == 429:
                if attempt == MAX_RETRIES:
                    raise HTTPException(
                        status_code=429,
                        detail="Gemini quota exceeded. Try again later."
                    )

                delay = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                jitter = random.uniform(0, delay * 0.3)
                await asyncio.sleep(delay + jitter)
                continue

            #  Bad payload or forbidden
            if status in (400, 403):
                raise HTTPException(
                    status_code=400,
                    detail="Gemini rejected the request payload"
                )

            #  too large
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

            # Fallback (unknown SDK error)
            raise HTTPException(
                status_code=502,
                detail=f"Unexpected Gemini error: {str(e)}"
            )
