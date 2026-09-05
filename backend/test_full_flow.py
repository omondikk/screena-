# test_two_devices.py
import httpx
import uuid
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
EMAIL = "test@crosssync.com"
PASSWORD = "TestPass123!"

def test_two_devices():
    print("🚀 Testing Two-Device Sync")
    print("="*50)
    
    # Login
    print("\n1️⃣ Logging in...")
    response = httpx.post(f"{BASE_URL}/auth/login", json={
        "email": EMAIL, 
        "password": PASSWORD
    })
    data = response.json()
    access_token = data["access_token"]
    print(f"✅ Logged in")
    
    # Device A
    device_a_id = str(uuid.uuid4())
    print(f"\n2️⃣ Device A: {device_a_id[:8]}...")
    
    # Register Device A
    httpx.post(
        f"{BASE_URL}/devices/register",
        params={"user_id": data["user_id"], "access_token": access_token},
        json={"device_name": "Device A", "device_type": "desktop"}
    )
    
    # Sync from Device A
    sync_data = {
        "content": f"Hello from Device A at {datetime.now().isoformat()}",
        "device_id": device_a_id,
        "content_hash": f"hash_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    }
    httpx.post(
        f"{BASE_URL}/clipboard/sync",
        params={"access_token": access_token},
        json=sync_data
    )
    print(f"   ✅ Synced from Device A")
    
    # Device B
    device_b_id = str(uuid.uuid4())
    print(f"\n3️⃣ Device B: {device_b_id[:8]}...")
    
    # Register Device B
    httpx.post(
        f"{BASE_URL}/devices/register",
        params={"user_id": data["user_id"], "access_token": access_token},
        json={"device_name": "Device B", "device_type": "desktop"}
    )
    
    # Device B fetches pending items
    response = httpx.get(
        f"{BASE_URL}/clipboard/sync/{device_b_id}",
        params={"access_token": access_token}
    )
    items = response.json().get("items", [])
    print(f"   ✅ Device B received {len(items)} items")
    for item in items:
        print(f"      Content: {item['content'][:50]}...")
    
    print("\n" + "="*50)
    print("✅ Two-device sync test complete!")

if __name__ == "__main__":
    test_two_devices()