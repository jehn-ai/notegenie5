import asyncio
import os
from fastapi import HTTPException
from openrouter import OpenRouter

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PRIMARY_MODEL = "openrouter/auto"
FALLBACK_MODEL = "meta-llama/llama-3-8b-instruct:free"

MAX_RETRIES = 3
RETRY_DELAY = 2  

# Initialize SDK client
client = OpenRouter(api_key=OPENROUTER_API_KEY)

async def call_openrouter_sdk(prompt: str, model: str = PRIMARY_MODEL, retries: int = MAX_RETRIES) -> str:
    """
    Calls OpenRouter SDK asynchronously with retries, fallback, and robust error handling.
    """
    for attempt in range(1, retries + 1):
        try:
            response = await client.completions.create(
                model=model,
                input=prompt,
                max_output_tokens=512
            )

            output = getattr(response, "output", None)
            if not output or not getattr(output[0], "content", None):
                raise HTTPException(status_code=500, detail="OpenRouter returned empty output")

            return output[0].content

        except Exception as e:
            # Retry only for transient errors
            transient_errors = ("timeout", "connection", "rate limit")
            if any(err.lower() in str(e).lower() for err in transient_errors) and attempt < retries:
                await asyncio.sleep(RETRY_DELAY * attempt)
                continue

            # Fallback to secondary model if primary fails
            if model != FALLBACK_MODEL:
                return await call_openrouter_sdk(prompt, model=FALLBACK_MODEL, retries=MAX_RETRIES)

            # Raise exception for FastAPI
            raise HTTPException(status_code=500, detail=f"OpenRouter SDK error: {str(e)}")
