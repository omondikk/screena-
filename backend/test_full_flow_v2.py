import httpx
import uuid
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
EMAIL = "test@crosssync.com"
PASSWORD = "TestPass123!"

def test_full_flow():
    print("🚀 CrossSync Complete Flow Test v2")
    print("="*50)
    
    # 1. Login
    print("\n1️⃣ Logging in...")
    login_data = {"email": EMAIL, "password": PASSWORD}
    response = httpx.post(f"{BASE_URL}/auth/login", json=login_data)
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.text}")
        return
    
    data = response.json()
    access_token = data["access_token"]
    user_id = data["user_id"]
    
    print(f"✅ Login successful!")
    print(f"   User ID: {user_id}")
    print(f"   Access Token: {access_token[:50]}...")
    
    # 2. Register a device with proper UUID
    print("\n2️⃣ Registering device...")
    device_id = str(uuid.uuid4())  # Generate proper UUID
    device_data = {
        "device_name": "My Windows PC",
        "device_type": "desktop"
    }
    
    response = httpx.post(
        f"{BASE_URL}/devices/register",
        params={"user_id": user_id, "access_token": access_token},
        json=device_data
    )
    
    if response.status_code == 200:
        result = response.json()
        device_id = result.get("device_id")
        print(f"✅ Device registered: {device_id}")
    else:
        print(f"⚠️ Device registration: {response.text}")
        print(f"   Using generated device ID: {device_id}")
    
    # 3. Sync clipboard content
    print("\n3️⃣ Syncing clipboard...")
    sync_data = {
        "content": f"CrossSync test at {datetime.now().isoformat()}",
        "device_id": device_id,
        "content_hash": f"hash_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    }
    
    response = httpx.post(
        f"{BASE_URL}/clipboard/sync",
        params={"access_token": access_token},
        json=sync_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Clipboard synced!")
        print(f"   ID: {result.get('id')}")
        print(f"   New: {result.get('is_new')}")
    else:
        print(f"❌ Sync failed: {response.text}")
        return
    
    # 4. Get pending sync items
    print("\n4️⃣ Fetching pending items...")
    response = httpx.get(
        f"{BASE_URL}/clipboard/sync/{device_id}",
        params={"access_token": access_token}
    )
    
    if response.status_code == 200:
        items = response.json().get("items", [])
        print(f"✅ Found {len(items)} items")
        for item in items[:3]:
            print(f"   - ID: {item.get('id')[:8]}...")
            print(f"     Content: {item.get('content', '')[:50]}...")
            print(f"     Created: {item.get('created_at')}")
            print()
    else:
        print(f"❌ Failed to fetch: {response.text}")
    
    # 5. Get all devices
    print("\n5️⃣ Getting all devices...")
    response = httpx.get(
        f"{BASE_URL}/devices",
        params={"user_id": user_id, "access_token": access_token}
    )
    
    if response.status_code == 200:
        devices = response.json().get("devices", [])
        print(f"✅ Found {len(devices)} devices")
        for device in devices:
            print(f"   - {device.get('device_name')} (ID: {device.get('id')[:8]}...)")
    else:
        print(f"⚠️ Could not get devices: {response.text}")
    
    print("\n" + "="*50)
    print("✅ Test complete!")

if __name__ == "__main__":
    test_full_flow()