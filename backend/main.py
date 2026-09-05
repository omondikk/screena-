from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from supabase import create_client, Client
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, List
import os
from datetime import datetime, timedelta
import uuid
import warnings
import base64
from cryptography.fernet import Fernet

warnings.filterwarnings("ignore")

app = FastAPI(
    title="CrossSync Clipboard API",
    version="1.0.0",
    description="Cross-device clipboard synchronization"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ Warning: Supabase credentials not set!")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase client initialized successfully")
except Exception as e:
    print(f"❌ Supabase initialization error: {e}")
    supabase = None

# ========== ENCRYPTION KEY (For Phone Viewer) ==========
ENCRYPTION_KEY = base64.urlsafe_b64encode(b"crosssync-clipboard-key-2024" + b"!" * 2)

# ========== PYDANTIC MODELS ==========
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    device_name: str

class DeviceRegister(BaseModel):
    device_name: str
    device_type: str = "desktop"

class ClipboardItem(BaseModel):
    content: str
    device_id: str
    content_hash: str

# ========== AUTH ROUTES ==========
@app.post("/auth/register")
async def register_user(user: UserRegister):
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
            "success": True,
            "message": "User registered successfully",
            "user_id": user_id,
            "device_id": device_id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/login")
async def login_user(user: UserLogin):
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
            "success": True,
            "user_id": response.user.id,
            "email": response.user.email,
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

# ========== USER INFO ROUTE ==========
@app.get("/auth/user")
async def get_user(access_token: str):
    """Get current user info"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {
            "id": user.user.id,
            "email": user.user.email,
            "created_at": user.user.created_at
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ========== DEVICE ROUTES ==========
@app.post("/devices/register")
async def register_device(device: DeviceRegister, user_id: str, access_token: str):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
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
        
        supabase.table("devices").insert(data).execute()
        return {"device_id": device_id, "message": "Device registered successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/devices")
async def get_devices(user_id: str, access_token: str):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
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

# ========== CLIPBOARD ROUTES ==========
@app.post("/clipboard/sync")
async def sync_clipboard(item: ClipboardItem, access_token: str):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = user.user.id
        
        # Check duplicate
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
        return {"message": "Synced successfully", "id": result.data[0]["id"], "is_new": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/clipboard/sync/{device_id}")
async def get_pending_sync(device_id: str, access_token: str):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = user.user.id
        
        result = supabase.table("clipboard_items")\
            .select("*")\
            .eq("user_id", user_id)\
            .neq("device_id", device_id)\
            .gt("expires_at", datetime.utcnow().isoformat())\
            .order("created_at", desc=True)\
            .limit(50)\
            .execute()
        
        return {"items": result.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ========== DECRYPT ENDPOINT (For Phone Viewer) ==========
@app.post("/decrypt")
async def decrypt_content(data: dict):
    """Decrypt encrypted clipboard content for phone viewer"""
    try:
        encrypted = data.get("encrypted", "")
        if not encrypted:
            return {"decrypted": ""}
        
        cipher = Fernet(ENCRYPTION_KEY)
        decrypted = cipher.decrypt(base64.urlsafe_b64decode(encrypted))
        return {"decrypted": decrypted.decode()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ========== PHONE VIEWER ==========
@app.get("/viewer")
async def serve_viewer():
    """Serve the phone viewer HTML page"""
    html_path = os.path.join(os.path.dirname(__file__), "phone_viewer.html")
    if os.path.exists(html_path):
        with open(html_path, "r") as f:
            return HTMLResponse(content=f.read())
    return {"error": "Viewer not found"}

# ========== HEALTH & ROOT ==========
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected" if supabase else "disconnected",
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    return {
        "name": "CrossSync Clipboard API",
        "version": "1.0.0",
        "status": "running",
        "database": "connected" if supabase else "disconnected",
        "docs": "/docs",
        "viewer": "/viewer"
    }