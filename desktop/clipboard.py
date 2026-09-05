from PySide6.QtCore import QObject, Signal
import pyperclip
import time
import threading

class ClipboardMonitor(QObject):
    clipboard_changed = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.is_running = False
        self.last_content = ""
        self.last_update_time = 0
        self.is_remote_update = False
        self.monitor_thread = None
        self.check_interval = 500
    
    def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        self.last_content = pyperclip.paste()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop(self):
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
    
    def _monitor_loop(self):
        while self.is_running:
            try:
                current_content = pyperclip.paste()
                
                if current_content != self.last_content:
                    if not self.is_remote_update:
                        self.last_content = current_content
                        self.last_update_time = time.time()
                        self.clipboard_changed.emit(current_content)
                    else:
                        self.is_remote_update = False
                        self.last_content = current_content
                
                time.sleep(self.check_interval / 1000.0)
                
            except Exception as e:
                print(f"Clipboard monitor error: {e}")
                time.sleep(1)
    
    def is_own_update(self) -> bool:
        return time.time() - self.last_update_time < 1.0
    
    def update_clipboard(self, content: str, is_remote: bool = False):
        self.is_remote_update = is_remote
        pyperclip.copy(content)
        self.last_content = content
        self.last_update_time = time.time()