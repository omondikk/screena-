import httpx
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"

def test_complete_flow():
    print("🚀 Testing Complete CrossSync Flow")
    print("="*50)
    
    # 1. Login with existing user
    print("\n1️⃣ Logging in...")
    login_data = {
        "email": "test@crosssync.com",
        "password": "TestPass123!"
    }
    
    response = httpx.post(f"{BASE_URL}/auth/login", json=login_data)
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.text}")
        return
    
    data = response.json()
    access_token = data.get("access_token")
    user_id = data.get("user_id")
    
    print(f"✅ Login successful!")
    print(f"   User ID: {user_id}")
    print(f"   Access Token: {access_token[:50]}...")
    
    # 2. Register a device (we need to do this through the API)
    print("\n2️⃣ Registering device...")
    device_data = {
        "device_name": "Test Windows PC",
        "device_type": "desktop"
    }
    
    response = httpx.post(
        f"{BASE_URL}/devices/register?user_id={user_id}&access_token={access_token}",
        json=device_data
    )
    
    if response.status_code == 200:
        device_data = response.json()
        device_id = device_data.get("device_id")
        print(f"✅ Device registered: {device_id}")
    else:
        print(f"⚠️ Device registration: {response.text}")
        device_id = "test-device-" + datetime.now().strftime("%H%M%S")
        print(f"   Using test device ID: {device_id}")
    
    # 3. Sync clipboard content
    print("\n3️⃣ Syncing clipboard...")
    sync_data = {
        "content": "Hello from CrossSync! This is a test sync at " + datetime.now().isoformat(),
        "device_id": device_id,
        "content_hash": "test_hash_123"
    }
    
    response = httpx.post(
        f"{BASE_URL}/clipboard/sync?access_token={access_token}",
        json=sync_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Clipboard synced!")
        print(f"   ID: {result.get('id')}")
        print(f"   New: {result.get('is_new')}")
    else:
        print(f"❌ Sync failed: {response.text}")
    
    # 4. Get pending sync items
    print("\n4️⃣ Fetching pending items...")
    response = httpx.get(
        f"{BASE_URL}/clipboard/sync/{device_id}?access_token={access_token}"
    )
    
    if response.status_code == 200:
        items = response.json().get("items", [])
        print(f"✅ Found {len(items)} items")
        for item in items[:3]:  # Show first 3
            print(f"   - ID: {item.get('id')} | Created: {item.get('created_at')}")
    else:
        print(f"❌ Failed to fetch: {response.text}")
    
    print("\n" + "="*50)
    print("✅ Test complete!")

if __name__ == "__main__":
    test_complete_flow()