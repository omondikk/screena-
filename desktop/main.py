import sys
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from desktop.tray import SystemTray
from desktop.clipboard import ClipboardMonitor
from desktop.sync import SyncManager
from desktop.crypto import CryptoManager
from desktop.config import Config
import threading

class CrossSyncApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        # Initialize components
        self.config = Config()
        self.crypto = CryptoManager()
        self.clipboard_monitor = ClipboardMonitor()
        self.sync_manager = SyncManager()
        self.tray = SystemTray()
        
        # Setup cleanup on exit
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Setup periodic tasks
        self.setup_timers()
        
        # Connect signals
        self.setup_connections()
    
    def setup_timers(self):
        """Setup periodic tasks"""
        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self.periodic_sync)
        self.sync_timer.start(5000)  # Sync every 5 seconds
    
    def setup_connections(self):
        """Setup signal-slot connections"""
        self.clipboard_monitor.clipboard_changed.connect(self.on_clipboard_changed)
        self.sync_manager.sync_completed.connect(self.on_sync_completed)
        self.sync_manager.sync_failed.connect(self.on_sync_failed)
        self.sync_manager.new_item_received.connect(self.on_new_item_received)
    
    def on_clipboard_changed(self, text):
        """Handle clipboard change event"""
        if not self.config.is_logged_in():
            return
        
        # Check if content should be ignored (passwords, sensitive data)
        if self.is_sensitive_content(text):
            return
        
        # Check if this is from our own device (prevent sync loops)
        if self.clipboard_monitor.is_own_update():
            return
        
        # Encrypt and sync
        import asyncio
        asyncio.create_task(self.handle_clipboard_change(text))
    
    async def handle_clipboard_change(self, text):
        """Encrypt and sync clipboard content"""
        try:
            # Generate content hash
            content_hash = self.crypto.hash_content(text)
            
            # Check if same content is already in sync
            if self.sync_manager.is_content_synced(content_hash):
                return
            
            # Encrypt content
            encrypted = self.crypto.encrypt(text)
            
            # Sync to server
            await self.sync_manager.sync_clipboard(encrypted, content_hash)
            
        except Exception as e:
            print(f"Error handling clipboard change: {e}")
    
    def periodic_sync(self):
        """Periodic sync to check for new items from other devices"""
        if not self.config.is_logged_in():
            return
        
        import asyncio
        asyncio.create_task(self.sync_manager.fetch_and_sync())
    
    def is_sensitive_content(self, text):
        """Check if content is sensitive (passwords, etc.)"""
        sensitive_patterns = [
            "password", "pass", "pwd", "secret", "token", "key",
            "credit card", "cvv", "ssn", "social security"
        ]
        
        text_lower = text.lower()
        for pattern in sensitive_patterns:
            if pattern in text_lower:
                return True
        
        if len(text) < 20 and any(c.isdigit() for c in text) and any(c.isupper() for c in text):
            if len(text) < 8:
                return True
        
        return False
    
    def on_sync_completed(self):
        """Handle sync completion"""
        self.tray.show_notification("Sync Complete", "Clipboard synchronized with other devices")
    
    def on_sync_failed(self, error):
        """Handle sync failure"""
        self.tray.show_notification("Sync Failed", f"Error: {error}")
    
    def on_new_item_received(self, content):
        """Handle new clipboard item received from other device"""
        # Decrypt content
        decrypted = self.crypto.decrypt(content)
        
        # Update local clipboard (mark as remote update to prevent loops)
        self.clipboard_monitor.update_clipboard(decrypted, is_remote=True)
        
        self.tray.show_notification("New Clipboard", "Content synced from another device")
    
    def signal_handler(self, signum, frame):
        """Handle system signals for clean shutdown"""
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self):
        """Cleanup resources before exit"""
        self.clipboard_monitor.stop()
        self.config.save()
    
    def run(self):
        """Run the application"""
        self.tray.show()
        self.clipboard_monitor.start()
        sys.exit(self.app.exec())

if __name__ == "__main__":
    app = CrossSyncApp()
    app.run()