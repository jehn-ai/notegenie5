from fastapi import APIRouter, Body
from app.services.summarizer import generate_summary

router = APIRouter()

@router.post("/summarize")
async def summarize_text(
    text: str = Body(...),
    summary_style: str = Body(...)
):
    
    summary = await generate_summary(text, summary_style)
    return{
        "summary_text":summary,
        "summary_style":summary_style
    }