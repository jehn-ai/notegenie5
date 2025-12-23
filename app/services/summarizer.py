from fastapi import HTTPException
from app.core.gemini_guard import gemini_semaphore, rpm_guard
from app.services.gemini_client import call_gemini
from app.utils.text_chucker import chunk_text
import os

Gemini_Api_Key = os.getenv("Gemini_Api_Key")
Model_Name = "gemini-2.0-flash-lite-001"

if not Gemini_Api_Key:
    raise RuntimeError("Gemini API Key not found. Check .env.")

ALLOWED_STYLES = ["Bullet", "Exam", "Detailed"]


def build_prompt(text: str, style: str) -> str:
    style_lower = style.lower()
    if style_lower not in [s.lower() for s in ALLOWED_STYLES]:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid summary style. Choose from: {ALLOWED_STYLES}"
        )

    # ⛔ PROMPT UNCHANGED (as requested)
    return f"""
You are an academic summarization assistant. Summarize the following text according to the user’s chosen style: "{style}". 
The summary must always follow these global academic standards:

1. Completeness – include all main ideas, key concepts, arguments, conclusions.
2. Accuracy – reflect the original content without adding interpretations.
3. Objectivity – maintain neutrality.
4. Paraphrasing – use your own words.
5. Coherence – logical, structured flow.
6. Brevity – reduce content to 10–30% of original length.
7. Citation – reference sources if provided.

Summary formats:
- bullet → concise bullet points for quick revision.
- exam → high-yield points, definitions, formulas, argument structure.
- detailed → well-structured academic paragraphs.

Text to summarize:
\"\"\"{text}\"\"\"
"""


# =========================
# Generate summary (RPM-safe, async-safe)

async def generate_summary(text: str, style: str) -> list[str]:
    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty.")

    chunks = chunk_text(text)

    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="No valid text chunks after preprocessing."
        )

    summaries: list[str] = []

    for chunk in chunks:
        prompt = build_prompt(chunk, style)

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ]
        }

        
        await rpm_guard()                # RPM ≤ 15
        async with gemini_semaphore:     # concurrency guard
            result = await call_gemini(
                Model_Name=Model_Name,
                payload=payload,
                Gemini_Api_Key=Gemini_Api_Key
            )

        try:
            text_out = (
                result["candidates"][0]
                ["content"]["parts"][0]["text"]
            )
            summaries.append(text_out)

        except (KeyError, IndexError):
            raise HTTPException(
                status_code=500,
                detail="Malformed response from Gemini API."
            )

    return summaries
