from fastapi import FastAPI
from app.services.supabase_client import supabase
from app.routes import upload, summary  # include summary routes

from middleware.error_handler import HideServerErrorsMiddleware

app = FastAPI(title="NoteGenie Backend", version="1.0.0")

# =========================
# Middleware
app.add_middleware(HideServerErrorsMiddleware)

# =========================
# Root endpoint
@app.get("/", tags=["Health"])
async def home():
    return {"message": "Notegenie Backend is running with uvicorn"}

# =========================
# Test Supabase connection
@app.get("/test-supabase", tags=["Health"])
async def test_supabase():
    try:
        users = supabase.table("users").select("*").execute()
        return {"users": users.data}
    except Exception as e:
        return {"error": str(e)}

# =========================
# Include routers
app.include_router(upload.router, prefix="/files", tags=["Upload"])
app.include_router(summary.router, prefix="/summary", tags=["Summary"])
