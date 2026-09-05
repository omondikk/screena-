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
    
    def _load_config(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def get_supabase_url(self):
        return "https://zqhmerojxldeqxdjdvqb.supabase.co"
    
    def get_supabase_key(self):
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpxaG1lcm9qeGxkZXF4ZGpkdnFiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg2MDY4MjYsImV4cCI6MjEwNDE4MjgyNn0.M5SaXF40-I2iByk1pOcQ7kIp1vzAKl0rGDrAok5An3o"
    
    def get_api_url(self):
        return self.data.get("api_url", "http://localhost:8000")
    
    def set_api_url(self, url):
        self.data["api_url"] = url
        self.save()
    
    def get_device_id(self):
        if "device_id" not in self.data:
            self.data["device_id"] = str(uuid.uuid4())
            self.save()
        return self.data["device_id"]
    
    def get_user_id(self):
        return self.data.get("user_id")
    
    def set_user_id(self, user_id):
        self.data["user_id"] = user_id
        self.save()
    
    def get_access_token(self):
        return self.data.get("access_token")
    
    def set_access_token(self, token):
        self.data["access_token"] = token
        self.save()
    
    def get_encryption_key(self):
        return self.data.get("encryption_key")
    
    def set_encryption_key(self, key):
        self.data["encryption_key"] = key
        self.save()
    
    def is_logged_in(self):
        return bool(self.data.get("access_token") and self.data.get("user_id"))
    
    def logout(self):
        if "access_token" in self.data:
            del self.data["access_token"]
        if "user_id" in self.data:
            del self.data["user_id"]
        self.save()