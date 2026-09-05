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
import secrets

# Configuration - Update this to your production URL
BASE_URL = "https://crosssync-backend.onrender.com"

class CrossSyncDesktop:
    def __init__(self):
        self.device_id = self.get_or_create_device_id()
        self.access_token = None
        self.last_content = ""
        self.synced_hashes = set()
        self.is_running = False
        self.encryption_key = self.get_or_create_key()
        self.cipher = Fernet(self.encryption_key)
        self.config_file = os.path.join(os.path.expanduser("~"), ".crosssync_config.json")
        self.load_config()
        
    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.device_id = config.get("device_id", self.device_id)
                    self.synced_hashes = set(config.get("synced_hashes", []))
        except:
            pass
    
    def save_config(self):
        try:
            config = {
                "device_id": self.device_id,
                "synced_hashes": list(self.synced_hashes)
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
        except:
            pass
    
    def get_or_create_device_id(self):
        config_file = os.path.join(os.path.expanduser("~"), ".crosssync_device.json")
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    return data.get("device_id")
        except:
            pass
        
        device_id = str(uuid.uuid4())
        try:
            with open(config_file, 'w') as f:
                json.dump({"device_id": device_id}, f)
        except:
            pass
        return device_id
    
    def get_or_create_key(self):
        """Get or create a valid Fernet encryption key"""
        key_file = os.path.join(os.path.expanduser("~"), ".crosssync_key.json")
        
        try:
            if os.path.exists(key_file):
                with open(key_file, 'r') as f:
                    data = json.load(f)
                    key = data.get("key", "")
                    if key and len(key) == 44:
                        return key.encode()
        except:
            pass
        
        # Generate a new Fernet key
        key = Fernet.generate_key()
        
        try:
            with open(key_file, 'w') as f:
                json.dump({"key": key.decode()}, f)
        except:
            pass
        
        return key
    
    def encrypt(self, text):
        if not text:
            return ""
        try:
            encrypted = self.cipher.encrypt(text.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            print(f"⚠️ Encryption error: {e}")
            return text
    
    def decrypt(self, encrypted_text):
        if not encrypted_text:
            return ""
        try:
            encrypted = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted = self.cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            return encrypted_text
    
    def hash_content(self, text):
        return hashlib.sha256(text.encode()).hexdigest()
    
    def login(self):
        print("\n🔐 Login Required")
        print("=" * 40)
        
        email = input("Email: ").strip()
        password = input("Password: ").strip()
        
        if not email or not password:
            print("❌ Email and password are required")
            return False
        
        try:
            response = httpx.post(
                f"{BASE_URL}/auth/login",
                json={"email": email, "password": password},
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                self.user_email = email
                print(f"✅ Logged in as: {email}")
                print(f"📱 Device ID: {self.device_id[:8]}...")
                return True
            else:
                print(f"❌ Login failed: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def register_device(self):
        try:
            response = httpx.get(
                f"{BASE_URL}/auth/user",
                params={"access_token": self.access_token}
            )
            if response.status_code != 200:
                print("⚠️ Could not verify user")
                return
            
            user_data = response.json()
            user_id = user_data.get("id")
            
            if not user_id:
                print("⚠️ Could not get user ID")
                return
            
            response = httpx.post(
                f"{BASE_URL}/devices/register",
                params={
                    "user_id": user_id,
                    "access_token": self.access_token
                },
                json={
                    "device_name": f"Desktop-{self.device_id[:8]}",
                    "device_type": "desktop"
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                print(f"✅ Device registered!")
            else:
                print(f"⚠️ Device registration: {response.text}")
        except Exception as e:
            print(f"⚠️ Error registering device: {e}")
    
    def sync_clipboard(self, content):
        try:
            encrypted = self.encrypt(content)
            content_hash = self.hash_content(content)
            
            if content_hash in self.synced_hashes:
                return
            
            sync_data = {
                "content": encrypted,
                "device_id": self.device_id,
                "content_hash": content_hash
            }
            
            response = httpx.post(
                f"{BASE_URL}/clipboard/sync",
                params={"access_token": self.access_token},
                json=sync_data,
                timeout=10.0
            )
            
            if response.status_code == 200:
                self.synced_hashes.add(content_hash)
                self.save_config()
                print(f"📤 Synced: {content[:30]}...")
                return True
            else:
                print(f"❌ Sync failed: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error syncing: {e}")
            return False
    
    def fetch_pending(self):
        try:
            response = httpx.get(
                f"{BASE_URL}/clipboard/sync/{self.device_id}",
                params={"access_token": self.access_token},
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                received_count = 0
                
                for item in items:
                    content_hash = item.get("content_hash")
                    if content_hash in self.synced_hashes:
                        continue
                    
                    encrypted_content = item.get("content")
                    decrypted = self.decrypt(encrypted_content)
                    
                    if decrypted:
                        pyperclip.copy(decrypted)
                        self.synced_hashes.add(content_hash)
                        self.save_config()
                        received_count += 1
                        print(f"📥 Received: {decrypted[:30]}...")
                
                if received_count > 0:
                    print(f"📥 Received {received_count} new items!")
                return len(items)
            else:
                return 0
        except Exception as e:
            print(f"⚠️ Error fetching: {e}")
            return 0
    
    def monitor_clipboard(self):
        print(f"\n🔍 Monitoring clipboard... (Press Ctrl+C to stop)")
        print(f"💻 Device: {self.device_id[:8]}...")
        print(f"🌐 Connected to: {BASE_URL}")
        print("=" * 50)
        
        self.last_content = pyperclip.paste()
        
        while self.is_running:
            try:
                current_content = pyperclip.paste()
                
                if current_content and current_content != self.last_content:
                    print(f"\n📋 Clipboard changed")
                    self.sync_clipboard(current_content)
                    self.last_content = current_content
                
                self.fetch_pending()
                time.sleep(2)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️ Error: {e}")
                time.sleep(2)
    
    def run(self):
        print("=" * 50)
        print("🔄 CrossSync Clipboard Desktop App")
        print("   Production Version 1.0.0")
        print("=" * 50)
        
        if not self.login():
            print("❌ Could not login. Please restart and try again.")
            input("Press Enter to exit...")
            return
        
        self.register_device()
        
        print("\n" + "=" * 50)
        print("🔄 CrossSync is running in the background")
        print("📋 Copy any text to sync across devices")
        print("=" * 50)
        
        self.is_running = True
        try:
            self.monitor_clipboard()
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down...")
        finally:
            self.is_running = False
            print("✅ CrossSync stopped")

if __name__ == "__main__":
    app = CrossSyncDesktop()
    app.run()