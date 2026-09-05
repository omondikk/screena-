# test_supabase.py - Test Supabase connection
from supabase import create_client
import os

SUPABASE_URL = "https://zqhmerojxldeqxdjdvqb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpxaG1lcm9qeGxkZXF4ZGpkdnFiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg2MDY4MjYsImV4cCI6MjEwNDE4MjgyNn0.M5SaXF40-I2iByk1pOcQ7kIp1vzAKl0rGDrAok5An3o"

try:
    print("Testing Supabase connection...")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Client created")
    
    # Try to list tables
    result = supabase.table("devices").select("*").limit(1).execute()
    print("✅ Table access successful")
    
    # Try to get database info
    print(f"✅ Connected to: {SUPABASE_URL}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("The supabase library might have compatibility issues with Python 3.14")
    print("Try installing an older version: pip install supabase==2.0.0")