from fastapi import FastAPI
from app.services.supabase_client import supabase
from app.routes import upload

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Notegenie Backend is running with uv"}


@app.get("/test-supabase")
def test_supabase():
    try:
        users = supabase.table("users").select("*").execute()
        return {"users": users.data}
    except Exception as e:
        return {"error": str(e)}
    
app.include_router(upload.router)
