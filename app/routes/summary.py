from fastapi import APIRouter, Body, HTTPException
from app.services.summarizer import summarize_text  # Use the correct function

router = APIRouter()

VALID_STYLES = ["Bullet", "Exam", "Detailed", "Flashcards"]

@router.post("/summarize")
async def summarize_endpoint(
    text: str = Body(..., embed=True),
    summary_style: str = Body(..., embed=True)
):
    # Validate style
    if summary_style not in VALID_STYLES:
        raise HTTPException(status_code=400, detail=f"Invalid summary style. Must be one of {VALID_STYLES}")

    # Call summarizer
    summary = await summarize_text(text, style=summary_style)
    
    return {
        "summary_text": summary,
        "summary_style": summary_style
    }
