from cryptography.fernet import Fernet
import base64
import hashlib
import os
from desktop.config import Config

class CryptoManager:
    def __init__(self):
        self.config = Config()
        self.key = self._get_or_create_key()
        self.cipher = Fernet(self.key)
    
    def _get_or_create_key(self):
        key = self.config.get_encryption_key()
        if key:
            return key.encode()
        
        # Generate new key
        salt = base64.b64encode(self.config.get_device_id().encode())[:16]
        key = base64.urlsafe_b64encode(os.urandom(32))
        
        self.config.set_encryption_key(key.decode())
        return key
    
    def encrypt(self, text: str) -> str:
        if not text:
            return ""
        encrypted = self.cipher.encrypt(text.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_text: str) -> str:
        if not encrypted_text:
            return ""
        encrypted = base64.urlsafe_b64decode(encrypted_text.encode())
        decrypted = self.cipher.decrypt(encrypted)
        return decrypted.decode()
    
    def hash_content(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()