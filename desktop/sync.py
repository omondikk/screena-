from PySide6.QtCore import QObject, Signal
import httpx
import asyncio
from desktop.config import Config

class SyncManager(QObject):
    sync_completed = Signal()
    sync_failed = Signal(str)
    new_item_received = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.config = Config()
        self.base_url = self.config.get_api_url()
        self.synced_items = set()
        self.is_syncing = False
    
    async def sync_clipboard(self, encrypted_content: str, content_hash: str):
        if self.is_syncing:
            return
        
        self.is_syncing = True
        
        try:
            device_id = self.config.get_device_id()
            access_token = self.config.get_access_token()
            
            if not device_id or not access_token:
                raise ValueError("Device or user not configured")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/clipboard/sync",
                    json={
                        "content": encrypted_content,
                        "device_id": device_id,
                        "content_hash": content_hash
                    },
                    params={"access_token": access_token}
                )
                
                if response.status_code == 200:
                    self.synced_items.add(content_hash)
                    self.sync_completed.emit()
                else:
                    raise Exception(f"Sync failed: {response.text}")
                
        except Exception as e:
            self.sync_failed.emit(str(e))
        finally:
            self.is_syncing = False
    
    async def fetch_and_sync(self):
        try:
            device_id = self.config.get_device_id()
            access_token = self.config.get_access_token()
            
            if not device_id or not access_token:
                return
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/clipboard/sync/{device_id}",
                    params={"access_token": access_token}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])
                    
                    for item in items:
                        if item["content_hash"] in self.synced_items:
                            continue
                        
                        self.new_item_received.emit(item["content"])
                        self.synced_items.add(item["content_hash"])
                    
                    if items:
                        self.sync_completed.emit()
                        
        except Exception as e:
            print(f"Error fetching sync: {e}")
    
    def is_content_synced(self, content_hash: str) -> bool:
        return content_hash in self.synced_items