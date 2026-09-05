from supabase import create_client
import os

# Your credentials
SUPABASE_URL = "https://zqhmerojxldeqxdjdvqb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpxaG1lcm9qeGxkZXF4ZGpkdnFiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg2MDY4MjYsImV4cCI6MjEwNDE4Mjg2fQ.M5SaXF40-I2iByk1pOcQ7kIp1vzAKl0rGDrAok5An3o"

# Test connection
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Try to list tables
    response = supabase.table("devices").select("*").limit(1).execute()
    print("✅ Connection successful!")
    print(f"✅ Table access works!")
    
    # Test auth (optional - only if you have a test user)
    # try:
    #     auth_response = supabase.auth.sign_in_with_password({
    #         "email": "test@example.com",
    #         "password": "testpassword123"
    #     })
    #     print("✅ Auth works!")
    # except:
    #     print("⚠️ Auth test skipped - no test user")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")