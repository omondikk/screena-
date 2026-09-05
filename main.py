from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import os
from datetime import datetime, timedelta
import uuid
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="CrossSync Clipboard API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Models
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

# Auth Routes
@app.post("/auth/register")
async def register_user(user: UserRegister):
    """Register a new user and register their first device"""
    try:
        # Register user with Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": user.email,
            "password": user.password
        })
        
        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Registration failed")
        
        user_id = auth_response.user.id
        
        # Register the device
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
    """Login user and return session"""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": user.email,
            "password": user.password
        })
        
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Update device last_active
        user_id = response.user.id
        supabase.table("devices")\
            .update({"last_active": datetime.utcnow().isoformat()})\
            .eq("user_id", user_id)\
            .eq("is_active", True)\
            .execute()
        
        return {
            "user_id": response.user.id,
            "email": response.user.email,
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/auth/logout")
async def logout_user(access_token: str):
    """Logout user"""
    try:
        supabase.auth.sign_out()
        return {"message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Device Routes
@app.post("/devices/register")
async def register_device(device: DeviceRegister, user_id: str, access_token: str):
    """Register a new device for a user"""
    try:
        # Verify the user exists
        supabase.auth.get_user(access_token)
        
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
    try:
        # Verify the user exists
        supabase.auth.get_user(access_token)
        
        result = supabase.table("devices")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("is_active", True)\
            .execute()
        return {"devices": result.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/devices/{device_id}/status")
async def update_device_status(device_id: str, is_active: bool, access_token: str):
    """Update device active status"""
    try:
        supabase.auth.get_user(access_token)
        
        result = supabase.table("devices")\
            .update({"is_active": is_active})\
            .eq("id", device_id)\
            .execute()
        return {"message": "Device status updated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Clipboard Routes
@app.post("/clipboard/sync")
async def sync_clipboard(item: ClipboardItem, access_token: str):
    """Sync clipboard content to server"""
    try:
        # Verify the user exists
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = user.user.id
        
        # Check for duplicate
        existing = supabase.table("clipboard_items")\
            .select("*")\
            .eq("content_hash", item.content_hash)\
            .eq("user_id", user_id)\
            .execute()
        
        if existing.data:
            # Update the existing item's expiration
            supabase.table("clipboard_items")\
                .update({"expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat()})\
                .eq("id", existing.data[0]["id"])\
                .execute()
            return {
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
        
        # Update sync state
        update_sync_state(item.device_id, result.data[0]["id"])
        
        return {
            "message": "Synced successfully",
            "id": result.data[0]["id"],
            "is_new": True
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/clipboard/sync/{device_id}")
async def get_pending_sync(device_id: str, access_token: str):
    """Get clipboard items pending for a device"""
    try:
        # Verify the user exists
        user = supabase.auth.get_user(access_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = user.user.id
        
        # Get last synced state
        sync_state = supabase.table("sync_state")\
            .select("*")\
            .eq("device_id", device_id)\
            .execute()
        
        last_synced_id = None
        if sync_state.data:
            last_synced_id = sync_state.data[0]["last_synced_item_id"]
        
        # Build query
        query = supabase.table("clipboard_items")\
            .select("*")\
            .eq("user_id", user_id)\
            .neq("device_id", device_id)\
            .gt("expires_at", datetime.utcnow().isoformat())
        
        if last_synced_id:
            # Get the timestamp of the last synced item
            last_sync = supabase.table("clipboard_items")\
                .select("created_at")\
                .eq("id", last_synced_id)\
                .execute()
            if last_sync.data:
                query = query.gt("created_at", last_sync.data[0]["created_at"])
        
        result = query.execute()
        
        # Order by created_at descending
        items = sorted(result.data, key=lambda x: x["created_at"], reverse=True)
        
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/clipboard/acknowledge/{device_id}/{item_id}")
async def acknowledge_sync(device_id: str, item_id: str, access_token: str):
    """Acknowledge that a device has received a clipboard item"""
    try:
        supabase.auth.get_user(access_token)
        update_sync_state(device_id, item_id)
        return {"message": "Acknowledged"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def update_sync_state(device_id: str, item_id: str):
    """Update sync state for a device"""
    try:
        # Check if sync state exists
        existing = supabase.table("sync_state")\
            .select("*")\
            .eq("device_id", device_id)\
            .execute()
        
        if existing.data:
            # Update existing
            supabase.table("sync_state")\
                .update({
                    "last_synced_item_id": item_id,
                    "updated_at": datetime.utcnow().isoformat()
                })\
                .eq("device_id", device_id)\
                .execute()
        else:
            # Insert new
            supabase.table("sync_state").insert({
                "device_id": device_id,
                "last_synced_item_id": item_id
            }).execute()
    except Exception as e:
        print(f"Error updating sync state: {e}")

# Health Check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/")
async def root():
    return {
        "name": "CrossSync Clipboard API",
        "version": "1.0.0",
        "status": "running"
    }