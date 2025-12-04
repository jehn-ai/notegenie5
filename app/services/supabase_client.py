from supabase import create_client, client
from dotenv import load_dotenv
import os


# load the env
load_dotenv()

# getting the key from .env
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")

print("supabase key:", SUPABASE_KEY)
print("supbase url:", SUPABASE_URL)

supabase: client = create_client(SUPABASE_URL,SUPABASE_KEY)
