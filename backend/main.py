from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import uuid
import warnings

warnings.filterwarnings("ignore")

app = FastAPI(title="CrossSync Clipboard API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase configuration
SUPABASE_URL = "https://zqhmerojxldeqxdjdvqb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpxaG1lcm9qeGxkZXF4ZGpkdnFiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg2MDY4MjYsImV4cCI6MjEwNDE4MjgyNn0.M5SaXF40-I2iByk1pOcQ7kIp1vzAKl0rGDrAok5An3o"

# Initialize Supabase client
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase client initialized successfully")
except Exception as e:
    print(f"❌ Supabase initialization error: {e}")
    supabase = None

# Models
class UserLogin(BaseModel):
    email: str
    password: str

class UserRegister(BaseModel):
    email: str
    password: str
    device_name: str

class DeviceRegister(BaseModel):
    device_name: str
    device_type: str = "desktop"

class ClipboardItem(BaseModel):
    content: str
    device_id: str
    content_hash: str

# Auth Routes
@app.post("/auth/register")
async def register_user(user: UserRegister):
    """Register a new user"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        auth_response = supabase.auth.sign_up({
            "email": user.email,
            "password": user.password
        })
        
        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Registration failed")
        
        user_id = auth_response.user.id
        
        # Register device
        device_id = str(uuid.uuid4())
        device_data = {
            "id": device_id,
            "user_id": user_id,
            "device_name": user.device_name,
            "device_type": "desktop",
            "is_active": True,
            "last_active": datetime.utcnow().isoformat()
        }
        
        supabase.table("devices").insert(device_data).execute()
        
        return {
            "message": "User registered successfully",
            "user_id": user_id,
            "device_id": device_id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/login")
async def login_user(user: UserLogin):
    """Login user"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        response = supabase.auth.sign_in_with_password({
            "email": user.email,
            "password": user.password
        })
        
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        return {
            "user_id": response.user.id,
            "email": response.user.email,
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

# Device Routes
@app.post("/devices/register")
async def register_device(device: DeviceRegister, user_id: str, access_token: str):
    """Register a new device for a user"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        # Verify the user exists
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        device_id = str(uuid.uuid4())
        data = {
            "id": device_id,
            "user_id": user_id,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "is_active": True,
            "last_active": datetime.utcnow().isoformat()
        }
        
        result = supabase.table("devices").insert(data).execute()
        return {
            "device_id": device_id,
            "message": "Device registered successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/devices")
async def get_devices(user_id: str, access_token: str):
    """Get all devices for a user"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        # Verify the user exists
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        result = supabase.table("devices")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("is_active", True)\
            .execute()
        return {"devices": result.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Clipboard Routes
@app.post("/clipboard/sync")
async def sync_clipboard(item: ClipboardItem, access_token: str):
    """Sync clipboard content"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = user.user.id
        
        # Check if device exists, if not create it
        device_check = supabase.table("devices")\
            .select("*")\
            .eq("id", item.device_id)\
            .execute()
        
        if not device_check.data:
            # Create device if it doesn't exist
            device_data = {
                "id": item.device_id,
                "user_id": user_id,
                "device_name": f"Device {item.device_id[:8]}",
                "device_type": "desktop",
                "is_active": True,
                "last_active": datetime.utcnow().isoformat()
            }
            supabase.table("devices").insert(device_data).execute()
        
        # Check for duplicate
        existing = supabase.table("clipboard_items")\
            .select("*")\
            .eq("content_hash", item.content_hash)\
            .eq("user_id", user_id)\
            .execute()
        
        if existing.data:
            return {
                "message": "Content already synced",
                "id": existing.data[0]["id"],
                "is_new": False
            }
        
        # Insert new item
        data = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "device_id": item.device_id,
            "content": item.content,
            "content_hash": item.content_hash,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat()
        }
        
        result = supabase.table("clipboard_items").insert(data).execute()
        
        return {
            "message": "Synced successfully",
            "id": result.data[0]["id"],
            "is_new": True
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/clipboard/sync/{device_id}")
async def get_pending_sync(device_id: str, access_token: str):
    """Get pending clipboard items"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = user.user.id
        
        # Get items not from this device
        result = supabase.table("clipboard_items")\
            .select("*")\
            .eq("user_id", user_id)\
            .neq("device_id", device_id)\
            .gt("expires_at", datetime.utcnow().isoformat())\
            .order("created_at", desc=True)\
            .execute()
        
        return {"items": result.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected" if supabase else "disconnected"
    }

@app.get("/")
async def root():
    return {
        "name": "CrossSync Clipboard API",
        "version": "1.0.0",
        "status": "running",
        "database": "connected" if supabase else "disconnected"
    }