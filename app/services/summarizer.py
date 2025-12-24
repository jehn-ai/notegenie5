from fastapi import HTTPException
from app.services.gemini_client import call_gemini
from app.utils.text_chucker import chunk_text

ALLOWED_STYLES = ["Bullet", "Exam", "Detailed"]

# =========================
# Prompt Builder (UNCHANGED LOGIC)
def build_prompt(text: str, style: str) -> str:
    if style.lower() not in [s.lower() for s in ALLOWED_STYLES]:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid summary style. Choose from: {ALLOWED_STYLES}"
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

# =========================
# Smart chunk merging
def merge_small_chunks(chunks, min_chars=800):
    """
    Merge small chunks into larger ones to reduce total Gemini requests.
    - min_chars: target minimum characters per chunk
    """
    if not chunks:
        return []

    merged_chunks = []
    buffer = ""

    for chunk in chunks:
        if len(buffer) + len(chunk) < min_chars:
            buffer += " " + chunk if buffer else chunk
        else:
            if buffer:
                merged_chunks.append(buffer)
            buffer = chunk

    if buffer:
        merged_chunks.append(buffer)

    return merged_chunks

# =========================
# Generate Summary (SDK-native, fully quota-aware, smart merge)
async def generate_summary(text: str, style: str) -> list[str]:
    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty.")

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="No valid text chunks after preprocessing."
        )

    # merge small chunks to reduce requests
    chunks = merge_small_chunks(chunks)

    all_summaries: list[str] = []

    for chunk in chunks:
        prompt = build_prompt(chunk, style)

        # Estimate tokens for this chunk (roughly: 1 token ≈ 4 chars)
        estimated_tokens = max(50, len(chunk) // 4)

        try:
            result = await call_gemini(prompt, estimated_tokens=estimated_tokens)
        except HTTPException as e:
            if e.status_code in (500, 502, 503):
                raise HTTPException(
                    status_code=503,
                    detail="AI service temporarily unavailable. Please retry."
                )
            elif e.status_code == 429:
                raise HTTPException(
                    status_code=429,
                    detail="Gemini quota exceeded. Try again later."
                )
            raise

        summaries = result.get("summary")
        if not summaries or not isinstance(summaries, list):
            raise HTTPException(
                status_code=502,
                detail="Gemini returned invalid structured summary."
            )

        all_summaries.extend(summaries)

    return all_summaries
