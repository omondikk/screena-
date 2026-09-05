import json
import os
import uuid
from pathlib import Path
from supabase import create_client, Client

class Config:
    def __init__(self):
        self.config_dir = Path.home() / ".crosssync"
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        self.data = self._load_config()
        
        # Initialize Supabase client
        self.supabase: Client = create_client(
            self.get_supabase_url(),
            self.get_supabase_key()
        )
    
    def _load_config(self):
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def get_supabase_url(self):
        """Get Supabase URL"""
        return "https://zqhmerojxldeqxdjdvqb.supabase.co"
    
    def get_supabase_key(self):
        """Get Supabase ANON key"""
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpxaG1lcm9qeGxkZXF4ZGpkdnFiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg2MDY4MjYsImV4cCI6MjEwNDE4MjgyNn0.M5SaXF40-I2iByk1pOcQ7kIp1vzAKl0rGDrAok5An3o"
    
    def get_api_url(self):
        """Get API base URL"""
        return self.data.get("api_url", "http://localhost:8000")
    
    def set_api_url(self, url):
        """Set API base URL"""
        self.data["api_url"] = url
        self.save()
    
    def get_device_id(self):
        """Get device ID"""
        if "device_id" not in self.data:
            self.data["device_id"] = str(uuid.uuid4())
            self.save()
        return self.data["device_id"]
    
    def get_user_id(self):
        """Get user ID"""
        return self.data.get("user_id")
    
    def set_user_id(self, user_id):
        """Set user ID"""
        self.data["user_id"] = user_id
        self.save()
    
    def get_access_token(self):
        """Get access token"""
        return self.data.get("access_token")
    
    def set_access_token(self, token):
        """Set access token"""
        self.data["access_token"] = token
        self.save()
    
    def get_refresh_token(self):
        """Get refresh token"""
        return self.data.get("refresh_token")
    
    def set_refresh_token(self, token):
        """Set refresh token"""
        self.data["refresh_token"] = token
        self.save()
    
    def get_encryption_key(self):
        """Get encryption key"""
        return self.data.get("encryption_key")
    
    def set_encryption_key(self, key):
        """Set encryption key"""
        self.data["encryption_key"] = key
        self.save()
    
    def is_logged_in(self):
        """Check if user is logged in"""
        return bool(self.data.get("access_token") and self.data.get("user_id"))
    
    def logout(self):
        """Logout user"""
        if "access_token" in self.data:
            del self.data["access_token"]
        if "user_id" in self.data:
            del self.data["user_id"]
        if "refresh_token" in self.data:
            del self.data["refresh_token"]
        self.save()