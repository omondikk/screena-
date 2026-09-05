from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict
import os
from datetime import datetime, timedelta
import uuid
import warnings
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore")

app = FastAPI(
    title="CrossSync Clipboard API",
    version="1.0.0",
    description="Cross-device clipboard synchronization"
)

# CORS - Allow all for now (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase configuration from environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", SUPABASE_KEY)

# Validate environment variables
if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Missing Supabase environment variables!")
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

# Initialize Supabase client
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("✅ Supabase client initialized successfully")
except Exception as e:
    logger.error(f"❌ Supabase initialization error: {e}")
    supabase = None

# Pydantic Models
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

class ClipboardResponse(BaseModel):
    id: str
    content: str
    device_id: str
    created_at: datetime
    expires_at: datetime

# ============== AUTH ROUTES ==============

@app.post("/auth/register", response_model=Dict)
async def register_user(user: UserRegister):
    """Register a new user with device"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        # Register with Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": user.email,
            "password": user.password
        })
        
        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Registration failed")
        
        user_id = auth_response.user.id
        
        # Create device for user
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
        logger.error(f"Registration error: {str(e)}")
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
        
        # Update device last_active
        user_id = response.user.id
        try:
            supabase.table("devices")\
                .update({"last_active": datetime.utcnow().isoformat()})\
                .eq("user_id", user_id)\
                .eq("is_active", True)\
                .execute()
        except Exception as e:
            logger.warning(f"Could not update device activity: {e}")
        
        return {
            "success": True,
            "user_id": response.user.id,
            "email": response.user.email,
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token
        }
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))

# ============== DEVICE ROUTES ==============

@app.post("/devices/register")
async def register_device(device: DeviceRegister, user_id: str, access_token: str):
    """Register a new device for a user"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        # Verify user
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
            "success": True,
            "device_id": device_id,
            "message": "Device registered successfully"
        }
    except Exception as e:
        logger.error(f"Device registration error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/devices")
async def get_devices(user_id: str, access_token: str):
    """Get all devices for a user"""
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
        logger.error(f"Get devices error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# ============== CLIPBOARD ROUTES ==============

@app.post("/clipboard/sync")
async def sync_clipboard(item: ClipboardItem, access_token: str):
    """Sync clipboard content to server"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        # Verify user
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = user.user.id
        
        # Ensure device exists
        device_check = supabase.table("devices")\
            .select("*")\
            .eq("id", item.device_id)\
            .execute()
        
        if not device_check.data:
            # Create device automatically
            device_data = {
                "id": item.device_id,
                "user_id": user_id,
                "device_name": f"Device {item.device_id[:8]}",
                "device_type": "desktop",
                "is_active": True,
                "last_active": datetime.utcnow().isoformat()
            }
            supabase.table("devices").insert(device_data).execute()
        
        # Check for duplicate by hash
        existing = supabase.table("clipboard_items")\
            .select("*")\
            .eq("content_hash", item.content_hash)\
            .eq("user_id", user_id)\
            .execute()
        
        if existing.data:
            return {
                "success": True,
                "message": "Content already synced",
                "id": existing.data[0]["id"],
                "is_new": False
            }
        
        # Insert new clipboard item
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
            "success": True,
            "message": "Synced successfully",
            "id": result.data[0]["id"],
            "is_new": True
        }
    except Exception as e:
        logger.error(f"Sync error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/clipboard/sync/{device_id}")
async def get_pending_sync(device_id: str, access_token: str):
    """Get pending clipboard items for a device"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = user.user.id
        
        # Get items from other devices
        result = supabase.table("clipboard_items")\
            .select("*")\
            .eq("user_id", user_id)\
            .neq("device_id", device_id)\
            .gt("expires_at", datetime.utcnow().isoformat())\
            .order("created_at", desc=True)\
            .limit(50)\
            .execute()
        
        return {
            "success": True,
            "items": result.data,
            "count": len(result.data)
        }
    except Exception as e:
        logger.error(f"Get pending error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# ============== HEALTH & STATUS ==============

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    db_status = "connected" if supabase else "disconnected"
    try:
        # Test database connection
        if supabase:
            supabase.table("devices").select("*").limit(1).execute()
            db_status = "connected"
    except:
        db_status = "disconnected"
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "CrossSync Clipboard API",
        "version": "1.0.0",
        "status": "running",
        "database": "connected" if supabase else "disconnected",
        "docs": "/docs"
    }