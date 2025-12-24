import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from PyPDF2 import PdfReader
from pdf2image import convert_from_bytes
import docx
import pytesseract

from app.services.summarizer import summarize_text  # updated function
from app.services.summarizer import chunk_text
from middleware.error_handler import HideServerErrorsMiddleware
from fastapi import FastAPI

app = FastAPI()
router = APIRouter()
executor = ThreadPoolExecutor()

# Allowed file types
ALLOWED_EXTENSIONS = ["pdf", "txt", "docx"]

# Protect API
app.add_middleware(HideServerErrorsMiddleware)

# =========================
# Text extraction
def extract_text(file: UploadFile) -> str:
    ext = file.filename.split(".")[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Allowed: {ALLOWED_EXTENSIONS}"
        )

    text = ""

    if ext == "txt":
        text = file.file.read().decode("utf-8")

    elif ext == "pdf":
        reader = PdfReader(file.file)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if not text.strip():
            # OCR fallback
            try:
                file.file.seek(0)
                images = convert_from_bytes(file.file.read())
                for img in images:
                    text += pytesseract.image_to_string(img) + "\n"
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"OCR failed: {e}")

    elif ext == "docx":
        doc = docx.Document(file.file)
        for para in doc.paragraphs:
            text += para.text + "\n"

    return text.strip()

# =========================
# Upload and summarize
@router.post("/upload")
async def upload_and_summarize(
    file: UploadFile = File(...),
    summary_style: str = Form(...)
):
    loop = asyncio.get_event_loop()

    # Extract text (CPU-bound in executor)
    text = await loop.run_in_executor(executor, extract_text, file)

    # Generate summary using the new OpenRouter-based summarizer
    summary = await summarize_text(text, style=summary_style)

    # Count chunks using the same logic as summarizer
    total_chunks = len(chunk_text(text))

    return {
        "file_name": file.filename,
        "file_type": file.content_type,
        "extracted_text_preview": text[:1000],
        "summary": summary,
        "summary_style": summary_style,
        "total_chunks": total_chunks
    }
