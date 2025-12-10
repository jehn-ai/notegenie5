from fastapi import APIRouter, HTTPException
import httpx
import os
import asyncio

router = APIRouter()
Gemini_Api_Key = os.getenv("Gemini_Api_Key")
Model_Name = "gemini-2.0-flash-lite-001"

# error handle
if not Gemini_Api_Key:
    raise RuntimeError("Gemini Key Not found, check .env.")

Alowed_style = ["Bullet", "Exam", "Detailed"]

# function for prompt NB: NGA means Notegenie Ai = Gemini
def build_prompt(text: str, style: str) -> str:
    style = style.lower()

    if style not in [s.lower() for s in Alowed_style]:
        raise HTTPException(
            status_code=422,
            detail=f"invaild summary style, chose from: {Alowed_style}",
        )
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


# RETRY + THROTTLE HELPER
MAX_RETRIES = 3     
THROTTLE_SECONDS = 2  

async def call_gemini_with_retry(url, payload):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            timeout = httpx.Timeout(120.0, read=120.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()  # success

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                print(f"Attempt {attempt} - Rate limited. Waiting {THROTTLE_SECONDS}s...")
                await asyncio.sleep(THROTTLE_SECONDS)
            else:
                raise HTTPException(status_code=500, detail=f"NGA API Request Failed: {e}")

    # all retries exhausted
    raise HTTPException(status_code=429, detail="Too Many Requests to NGA API, please try later.")


# function for summary generation
async def generate_summary(text: str, style: str) -> str:
    if not text.strip():
        raise HTTPException(
            status_code=422, detail="Text cannot be empty, Upload a file with content"
        )
    prompt = build_prompt(text, style)

    url = (
       f"https://generativelanguage.googleapis.com/v1beta/models/{Model_Name}:generateContent?key={Gemini_Api_Key}"
    )

    payload = {
        "contents":[
            {
                "parts":[
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature":0
        }
    }

    # call Gemini with retry + throttle
    data = await call_gemini_with_retry(url, payload)

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise HTTPException(status_code=500, detail="unexpected error from NGA")
