import sys
import time
import pyperclip
import httpx
import uuid
import hashlib
import json
from datetime import datetime
from cryptography.fernet import Fernet
import base64
import os
import threading

# Configuration
BASE_URL = "http://127.0.0.1:8000"
EMAIL = "test@crosssync.com"
PASSWORD = "TestPass123!"

class CrossSyncDesktop:
    def __init__(self):
        self.device_id = str(uuid.uuid4())
        self.access_token = None
        self.last_content = ""
        self.synced_hashes = set()
        self.is_running = False
        self.encryption_key = self.get_or_create_key()
        self.cipher = Fernet(self.encryption_key)
        
    def get_or_create_key(self):
        """Get or create a valid Fernet encryption key"""
        # Create a proper 32-byte key
        # Method 1: Use a fixed string padded to 32 bytes
        raw_key = b"crosssync-clipboard-key-2024"  # 30 bytes
        # Pad to 32 bytes
        while len(raw_key) < 32:
            raw_key += b"!"
        raw_key = raw_key[:32]  # Ensure exactly 32 bytes
        
        # Base64 encode for Fernet
        key = base64.urlsafe_b64encode(raw_key)
        return key
    
    def encrypt(self, text):
        """Encrypt clipboard content"""
        if not text:
            return ""
        try:
            encrypted = self.cipher.encrypt(text.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            print(f"⚠️ Encryption error: {e}")
            return text
    
    def decrypt(self, encrypted_text):
        """Decrypt clipboard content"""
        if not encrypted_text:
            return ""
        try:
            encrypted = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted = self.cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            print(f"⚠️ Decryption error: {e}")
            return encrypted_text
    
    def hash_content(self, text):
        """Generate hash for content"""
        return hashlib.sha256(text.encode()).hexdigest()
    
    def login(self):
        """Login to the backend"""
        try:
            response = httpx.post(
                f"{BASE_URL}/auth/login",
                json={"email": EMAIL, "password": PASSWORD},
                timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                print(f"✅ Logged in! Device ID: {self.device_id[:8]}...")
                return True
            else:
                print(f"❌ Login failed: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def register_device(self):
        """Register this device"""
        try:
            response = httpx.post(
                f"{BASE_URL}/devices/register",
                params={
                    "user_id": "ac011d70-d811-42b7-b145-1ab3820d92d6",
                    "access_token": self.access_token
                },
                json={
                    "device_name": f"Desktop-{self.device_id[:8]}",
                    "device_type": "desktop"
                },
                timeout=5.0
            )
            if response.status_code == 200:
                print(f"✅ Device registered!")
                return True
            else:
                print(f"⚠️ Device registration: {response.text}")
                return False
        except Exception as e:
            print(f"⚠️ Error registering device: {e}")
            return False
    
    def sync_clipboard(self, content):
        """Sync clipboard content to server"""
        try:
            # Encrypt content
            encrypted = self.encrypt(content)
            content_hash = self.hash_content(content)
            
            # Check if already synced
            if content_hash in self.synced_hashes:
                return
            
            # Sync to server
            sync_data = {
                "content": encrypted,
                "device_id": self.device_id,
                "content_hash": content_hash
            }
            
            response = httpx.post(
                f"{BASE_URL}/clipboard/sync",
                params={"access_token": self.access_token},
                json=sync_data,
                timeout=5.0
            )
            
            if response.status_code == 200:
                self.synced_hashes.add(content_hash)
                print(f"📤 Synced: {content[:30]}...")
                return True
            else:
                print(f"❌ Sync failed: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error syncing: {e}")
            return False
    
    def fetch_pending(self):
        """Fetch pending clipboard items from other devices"""
        try:
            response = httpx.get(
                f"{BASE_URL}/clipboard/sync/{self.device_id}",
                params={"access_token": self.access_token},
                timeout=5.0
            )
            
            if response.status_code == 200:
                items = response.json().get("items", [])
                received_count = 0
                
                for item in items:
                    content_hash = item.get("content_hash")
                    if content_hash in self.synced_hashes:
                        continue
                    
                    # Decrypt content
                    encrypted_content = item.get("content")
                    decrypted = self.decrypt(encrypted_content)
                    
                    if decrypted:
                        # Update local clipboard
                        pyperclip.copy(decrypted)
                        self.synced_hashes.add(content_hash)
                        received_count += 1
                        print(f"📥 Received: {decrypted[:30]}...")
                
                if received_count > 0:
                    print(f"📥 Received {received_count} new items!")
                return len(items)
            else:
                return 0
        except Exception as e:
            print(f"❌ Error fetching: {e}")
            return 0
    
    def monitor_clipboard(self):
        """Monitor clipboard for changes"""
        print(f"\n🔍 Monitoring clipboard... (Press Ctrl+C to stop)")
        print(f"📋 Current clipboard preview: {pyperclip.paste()[:50]}...")
        self.last_content = pyperclip.paste()
        
        while self.is_running:
            try:
                current_content = pyperclip.paste()
                
                # Check if clipboard changed
                if current_content and current_content != self.last_content:
                    print(f"\n📋 Clipboard changed: {current_content[:30]}...")
                    
                    # Sync the new content
                    self.sync_clipboard(current_content)
                    self.last_content = current_content
                
                # Check for pending items from other devices
                self.fetch_pending()
                
                time.sleep(2)  # Check every 2 seconds
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(1)
    
    def run(self):
        """Run the desktop app"""
        print("="*50)
        print("🔄 CrossSync Clipboard Desktop App")
        print("="*50)
        
        # Login and setup
        if not self.login():
            print("❌ Could not login. Please check your credentials.")
            return
        
        self.register_device()
        
        # Start monitoring
        self.is_running = True
        try:
            self.monitor_clipboard()
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down...")
        finally:
            self.is_running = False

if __name__ == "__main__":
    app = CrossSyncDesktop()
    app.run()