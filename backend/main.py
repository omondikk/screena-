from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from supabase import create_client, Client
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, List, Any
import os
from datetime import datetime, timedelta
import uuid
import warnings
import json
import logging

# ========== LOGGING SETUP ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore")

# ========== FASTAPI APP ==========
app = FastAPI(
    title="CrossSync Clipboard API",
    version="2.0.0",
    description="Cross-device clipboard synchronization - Large content optimized"
)

# Add GZip compression for faster responses (compress >1KB)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS - Allow all origins for testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== SUPABASE CONFIGURATION ==========
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://zqhmerojxldeqxdjdvqb.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.warning("⚠️ Supabase credentials not set!")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("✅ Supabase client initialized successfully")
except Exception as e:
    logger.error(f"❌ Supabase initialization error: {e}")
    supabase = None

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
    content: str = Field(..., max_length=10 * 1024 * 1024)  # 10MB max
    device_id: str
    content_hash: str

class ClipboardResponse(BaseModel):
    id: str
    user_id: str
    device_id: str
    content: str
    content_hash: str
    created_at: str
    expires_at: str

# ========== AUTH ROUTES ==========
@app.post("/auth/register", response_model=Dict)
async def register_user(user: UserRegister):
    """Register a new user with device"""
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
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/login", response_model=Dict)
async def login_user(user: UserLogin):
    """Login user and return access token"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        response = supabase.auth.sign_in_with_password({
            "email": user.email,
            "password": user.password
        })
        
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Update device activity
        try:
            supabase.table("devices")\
                .update({"last_active": datetime.utcnow().isoformat()})\
                .eq("user_id", response.user.id)\
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

@app.get("/auth/user", response_model=Dict)
async def get_user(access_token: str):
    """Get current user info from token"""
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
        logger.error(f"Get user error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# ========== DEVICE ROUTES ==========
@app.post("/devices/register", response_model=Dict)
async def register_device(device: DeviceRegister, user_id: str, access_token: str):
    """Register a new device for a user"""
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
        return {
            "device_id": device_id,
            "message": "Device registered successfully"
        }
    except Exception as e:
        logger.error(f"Device registration error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/devices", response_model=Dict)
async def get_devices(user_id: str, access_token: str):
    """Get all active devices for a user"""
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

# ========== CLIPBOARD ROUTES ==========
@app.post("/clipboard/sync")
async def sync_clipboard(item: ClipboardItem, access_token: str, request: Request):
    """Sync clipboard content - optimized for large content up to 10MB"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        # Log incoming request size
        content_size = len(item.content)
        logger.info(f"📥 Sync request: {content_size} bytes from device {item.device_id[:8]}...")
        
        # Validate content size
        if content_size > 10 * 1024 * 1024:  # 10MB
            logger.warning(f"⚠️ Content too large: {content_size} bytes")
            raise HTTPException(status_code=413, detail="Content too large (max 10MB)")
        
        # Verify user
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = user.user.id
        
        # Check for duplicate
        existing = supabase.table("clipboard_items")\
            .select("id")\
            .eq("content_hash", item.content_hash)\
            .eq("user_id", user_id)\
            .execute()
        
        if existing.data:
            logger.info(f"⏭️ Duplicate content, skipping")
            return {
                "message": "Content already synced",
                "id": existing.data[0]["id"],
                "is_new": False
            }
        
        # Create entry
        data = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "device_id": item.device_id,
            "content": item.content,  # Store plain text
            "content_hash": item.content_hash,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat()
        }
        
        # Insert into database
        result = supabase.table("clipboard_items").insert(data).execute()
        
        logger.info(f"✅ Saved: {content_size} bytes, ID: {result.data[0]['id']}")
        
        return {
            "message": "Synced successfully",
            "id": result.data[0]["id"],
            "is_new": True,
            "size": content_size
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Sync error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/clipboard/sync/{device_id}")
async def get_pending_sync(
    device_id: str, 
    access_token: str, 
    limit: int = 50, 
    offset: int = 0,
    request: Request
):
    """Get pending clipboard items - optimized with pagination"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        # Verify user
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = user.user.id
        
        # Ensure limit is reasonable
        if limit > 100:
            limit = 100
        
        # Get items from other devices
        result = supabase.table("clipboard_items")\
            .select("*")\
            .eq("user_id", user_id)\
            .neq("device_id", device_id)\
            .gt("expires_at", datetime.utcnow().isoformat())\
            .order("created_at", desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        
        # Count total
        count_result = supabase.table("clipboard_items")\
            .select("id", count="exact")\
            .eq("user_id", user_id)\
            .neq("device_id", device_id)\
            .gt("expires_at", datetime.utcnow().isoformat())\
            .execute()
        
        total_count = count_result.count if count_result else 0
        
        # Log response size
        total_size = sum(len(item.get("content", "")) for item in result.data)
        logger.info(f"📤 Fetch: {len(result.data)} items, {total_size} bytes total")
        
        return {
            "items": result.data,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "size": total_size
        }
    except Exception as e:
        logger.error(f"Get pending error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# ========== CLEAR ALL DATA ENDPOINT ==========
@app.delete("/clipboard/clear_all")
async def clear_all_clipboard(access_token: str):
    """Delete ALL clipboard items for the user"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        # Verify user
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = user.user.id
        
        # Count items before deletion
        count_result = supabase.table("clipboard_items")\
            .select("id", count="exact")\
            .eq("user_id", user_id)\
            .execute()
        
        total_before = count_result.count if count_result else 0
        
        # Delete ALL items for this user
        result = supabase.table("clipboard_items")\
            .delete()\
            .eq("user_id", user_id)\
            .execute()
        
        deleted_count = len(result.data)
        
        # Also clear sync state for this user's devices
        supabase.table("sync_state")\
            .delete()\
            .eq("user_id", user_id)\
            .execute()
        
        logger.info(f"🗑️ Cleared {deleted_count} items for user {user_id}")
        
        return {
            "message": f"Deleted {deleted_count} items",
            "deleted": deleted_count,
            "total_before": total_before
        }
    except Exception as e:
        logger.error(f"Clear all error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# ========== CLEANUP OLD ITEMS (Optional) ==========
@app.delete("/clipboard/cleanup")
async def cleanup_old_items(access_token: str, days: int = 1):
    """Delete clipboard items older than specified days"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
    
    try:
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = user.user.id
        
        # Delete items older than 'days'
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        result = supabase.table("clipboard_items")\
            .delete()\
            .eq("user_id", user_id)\
            .lt("created_at", cutoff_date)\
            .execute()
        
        return {
            "deleted": len(result.data),
            "message": f"Deleted {len(result.data)} items older than {days} day(s)"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ========== HEALTH & STATUS ==========
@app.get("/health", response_model=Dict)
async def health_check():
    """Health check endpoint"""
    db_status = "connected" if supabase else "disconnected"
    try:
        if supabase:
            supabase.table("devices").select("id").limit(1).execute()
            db_status = "connected"
    except:
        db_status = "disconnected"
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "version": "2.0.0",
        "max_content_size": "10MB"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "CrossSync Clipboard API",
        "version": "2.0.0",
        "status": "running",
        "database": "connected" if supabase else "disconnected",
        "docs": "/docs",
        "viewer": "/viewer",
        "max_content_size": "10MB"
    }

# ========== PHONE VIEWER ==========
@app.get("/viewer", response_class=HTMLResponse)
async def serve_viewer():
    """Serve the phone viewer HTML page"""
    html_path = os.path.join(os.path.dirname(__file__), "phone_viewer.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Viewer not found</h1>", status_code=404)

# ========== CUSTOM EXCEPTION HANDLERS ==========
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# ========== STARTUP EVENT ==========
@app.on_event("startup")
async def startup_event():
    """Run on startup"""
    logger.info("🚀 CrossSync API starting up...")
    logger.info(f"📊 Database: {'connected' if supabase else 'disconnected'}")
    logger.info(f"📋 Max content size: 10MB")
    logger.info("✅ API ready")

@app.on_event("shutdown")
async def shutdown_event():
    """Run on shutdown"""
    logger.info("👋 CrossSync API shutting down...")