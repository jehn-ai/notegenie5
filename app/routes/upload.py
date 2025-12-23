from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi import FastAPI
from PyPDF2 import PdfReader
from pdf2image import convert_from_bytes
from concurrent.futures import ThreadPoolExecutor
from app.services.summarizer import generate_summary
from middleware.error_handler import HideServerErrorsMiddleware
from app.utils.text_chucker import chunk_text
import docx
import asyncio
import pytesseract
# from PIL import Image

app = FastAPI()
router = APIRouter()
executor = ThreadPoolExecutor()

#set of allowed file format
Allowed_Extension=["pdf","txt","docx"]
#adding a protect api
app.add_middleware(HideServerErrorsMiddleware)

#extraction function

def extract_text(file: UploadFile):
    ext = file.filename.split(".")[-1].lower() #makes the extracted text all in lower caps
    if ext not in Allowed_Extension:
        raise HTTPException(status_code=404,detail= f"The Uploaded File Format is not supported,Try: {Allowed_Extension} ")
    
    text = ""
#extract for text
    if ext == "txt":
        text = file.file.read().decode("utf-8") 
#extract for pdf
    elif ext == "pdf":
        reader = PdfReader(file.file)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if not text.strip():
            try:
                file.file.seek(0)
                images = convert_from_bytes(file.file.read())
                for img in images:
                    text += pytesseract.image_to_string(img) + "\n"
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"OCR failed: {e}")
            
        
#doc extract
    elif ext == "docx":
        doc = docx.Document(file.file)
        for para in doc.paragraphs:
            text += para.text + "\n"
#image to text (been removed for now)
    # elif ext in ["png","jpeg","jpg"]:
    #     try:
    #         image = Image.open(file.file)
    #         text= pytesseract.image_to_string(image)
    #     except Exception as e:
    #         raise HTTPException(status_code=500,detail=f"OCR Failed {e}")

     

    return text.strip()
#push the uploaded file to the server/api
@router.post("/upload")
async def upload_and_summarize(file: UploadFile = File(...), summary_style: str = Form(...),embed=True):
    loop = asyncio.get_event_loop()

    #extract the text
    text = await loop.run_in_executor(executor, extract_text,file)
    #generate summary
    summary_list = await generate_summary(text, summary_style)
    

    return {
    "file_name": file.filename,
    "file_type": file.content_type,
    "extracted_text_preview": text[:1000],
    "summary": summary_list,
    "summary_style": summary_style,
    "total_chunks": len(chunk_text(text)),
}







