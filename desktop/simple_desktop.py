import sys
import time
import pyperclip
import httpx
import uuid
import hashlib
import json
from datetime import datetime
import os
import threading

# Configuration
BASE_URL = "https://crosssync-backend.onrender.com"

class CrossSyncDesktop:
    def __init__(self):
        self.device_id = self.get_or_create_device_id()
        self.access_token = None
        self.last_content = ""
        self.last_content_hash = ""
        self.synced_hashes = set()
        self.is_running = False
        self.config_file = os.path.join(os.path.expanduser("~"), ".crosssync_config.json")
        self.load_config()
        self.sync_count = 0
        self.received_count = 0
        self.last_clipboard_check = ""
        
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
    
    def get_clipboard_content(self):
        """Safely get clipboard content with retry"""
        try:
            # First attempt
            content = pyperclip.paste()
            
            # If content is suspiciously short, wait and retry
            if len(content) < 100 and content != self.last_content:
                time.sleep(0.1)
                content = pyperclip.paste()
                
            return content
        except Exception as e:
            print(f"⚠️ Clipboard read error: {e}")
            return ""
    
    def hash_content(self, text):
        return hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest()
    
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
        """Sync plain text - NO encryption"""
        try:
            content_size = len(content)
            
            # Check content size (10MB limit)
            if content_size > 10 * 1024 * 1024:
                print(f"⚠️ Content too large ({content_size} bytes), skipping...")
                return False
            
            # Get hash
            content_hash = self.hash_content(content)
            
            # Check if already synced
            if content_hash in self.synced_hashes:
                print(f"⏭️ Already synced (hash: {content_hash[:8]}...)")
                return False
            
            # Check if this is the same as last content but different hash
            if self.last_content_hash == content_hash:
                print(f"⏭️ Duplicate content, skipping")
                return False
            
            sync_data = {
                "content": content,
                "device_id": self.device_id,
                "content_hash": content_hash
            }
            
            # Show upload progress for large content
            if content_size > 1024 * 1024:  # > 1MB
                print(f"📤 Uploading {content_size / 1024 / 1024:.2f} MB...")
            
            response = httpx.post(
                f"{BASE_URL}/clipboard/sync",
                params={"access_token": self.access_token},
                json=sync_data,
                timeout=60.0  # Increased for large content
            )
            
            if response.status_code == 200:
                self.synced_hashes.add(content_hash)
                self.last_content_hash = content_hash
                self.save_config()
                self.sync_count += 1
                
                # Show preview with size
                if content_size > 100:
                    preview = content[:100] + "..."
                else:
                    preview = content
                    
                print(f"📤 Synced [{self.sync_count}]: {preview}")
                print(f"   📊 Size: {content_size} bytes ({content_size / 1024:.1f} KB)")
                return True
            else:
                print(f"❌ Sync failed: {response.text}")
                return False
        except httpx.TimeoutException:
            print(f"❌ Sync timeout - content may be too large")
            return False
        except Exception as e:
            print(f"❌ Error syncing: {e}")
            return False
    
    def fetch_pending(self):
        """Fetch plain text - NO decryption needed"""
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
                    
                    content = item.get("content", "")
                    if content:
                        # Copy to clipboard
                        try:
                            pyperclip.copy(content)
                            self.synced_hashes.add(content_hash)
                            self.save_config()
                            received_count += 1
                            self.received_count += 1
                            
                            content_size = len(content)
                            preview = content[:100] + "..." if content_size > 100 else content
                            print(f"📥 Received [{self.received_count}]: {preview}")
                            print(f"   📊 Size: {content_size} bytes ({content_size / 1024:.1f} KB)")
                        except Exception as e:
                            print(f"⚠️ Error copying to clipboard: {e}")
                
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
        print(f"📋 Max content size: 10MB")
        print("=" * 50)
        
        self.last_content = self.get_clipboard_content()
        self.last_content_hash = self.hash_content(self.last_content)
        
        while self.is_running:
            try:
                # Read clipboard with retry for large content
                current_content = self.get_clipboard_content()
                
                if current_content and current_content != self.last_content:
                    content_len = len(current_content)
                    
                    # Show what was detected
                    if content_len > 100:
                        preview = current_content[:100] + "..."
                    else:
                        preview = current_content
                        
                    print(f"\n📋 Clipboard changed")
                    print(f"   📊 Size: {content_len} characters")
                    print(f"   📝 Preview: {preview}")
                    
                    # Verify it's text and not just whitespace
                    if isinstance(current_content, str) and current_content.strip():
                        self.sync_clipboard(current_content)
                    else:
                        print(f"⚠️ Empty or whitespace content ignored")
                    
                    self.last_content = current_content
                    self.last_content_hash = self.hash_content(current_content)
                
                self.fetch_pending()
                time.sleep(1)  # Check more frequently
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️ Monitor error: {e}")
                time.sleep(2)
    
    def run(self):
        print("=" * 50)
        print("🔄 CrossSync Clipboard Desktop App")
        print("   Production Version 2.1.0")
        print("=" * 50)
        
        if not self.login():
            print("❌ Could not login. Please restart and try again.")
            input("Press Enter to exit...")
            return
        
        self.register_device()
        
        print("\n" + "=" * 50)
        print("🔄 CrossSync is running in the background")
        print("📋 Copy any text to sync across devices")
        print("💡 Tip: For large content, wait a moment after copying")
        print("=" * 50)
        
        self.is_running = True
        try:
            self.monitor_clipboard()
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down...")
        finally:
            self.is_running = False
            print(f"\n📊 Summary:")
            print(f"   📤 Synced: {self.sync_count} items")
            print(f"   📥 Received: {self.received_count} items")
            print("✅ CrossSync stopped")

if __name__ == "__main__":
    app = CrossSyncDesktop()
    app.run()