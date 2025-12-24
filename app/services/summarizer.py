import json
import os
import math
import asyncio
from typing import List
from fastapi import HTTPException
from openrouter_client import call_openrouter_sdk  # Your client from earlier

# =========================
# Load dynamic prompts from JSON
PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts.json")

with open(PROMPT_FILE, "r", encoding="utf-8") as f:
    PROMPTS = json.load(f)

# =========================
# Chunking helper
def chunk_text(text: str, max_words: int = 200) -> List[str]:
   
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i + max_words])
        chunks.append(chunk)
    return chunks

# =========================
# Smart merge helper
def smart_merge(summaries: List[str]) -> str:
    
    # Simple approach: join with double newline
    return "\n\n".join(summaries)

# =========================
# Build prompt dynamically
def build_prompt(text_chunk: str, style: str) -> str:
   
    if style not in PROMPTS:
        raise HTTPException(status_code=400, detail=f"Invalid summary style: {style}")
    
    template = PROMPTS[style]
    return template.replace("{TEXT_CHUNK}", text_chunk)

# =========================
# Main summarizer
async def summarize_text(text: str, style: str = "Bullet") -> str:
   
    # 1. Chunk text
    chunks = chunk_text(text, max_words=200)
    
    # 2. Prepare tasks for async OpenRouter calls
    tasks = []
    for chunk in chunks:
        prompt = build_prompt(chunk, style)
        tasks.append(call_openrouter_sdk(prompt))

    try:
        # 3. Call OpenRouter on all chunks concurrently
        chunk_summaries = await asyncio.gather(*tasks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")
    
    # 4. Smart merge summaries
    final_summary = smart_merge(chunk_summaries)
    
    return final_summary

# =================
# Optional: helper for flashcards (if style=Flashcards)
async def generate_flashcards(text: str) -> str:
    return await summarize_text(text, style="Flashcards")
