import asyncio
import os
from supabase._async.client import AsyncClient

os.environ["SUPABASE_URL"] = "http://localhost:8000"
os.environ["SUPABASE_SERVICE_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJmY2Vqbm1ycnltZW1rcnduam9nIiwicm9sZSI6ImFub24iLCJpYXQiOjE2MjY4NjcxNzgsImV4cCI6MTk0MjQ0MzE3OH0.fake_key"
client = AsyncClient(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
print(client)
