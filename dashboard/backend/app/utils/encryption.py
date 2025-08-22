"""
Encryption utilities for sensitive data
"""

import os
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class EncryptionManager:
    """Manages encryption and decryption of sensitive data"""
    
    def __init__(self):
        self._cipher = None
        self._initialize_cipher()
    
    def _initialize_cipher(self):
        """Initialize the encryption cipher"""
        # Get encryption key from environment
        encryption_key = os.getenv('ENCRYPTION_KEY')
        
        if not encryption_key:
            # Generate a development key (should not be used in production)
            encryption_key = 'development-encryption-key-32chr'
            logger.warning("Using development encryption key. Set ENCRYPTION_KEY for production.")
        
        # Derive a proper encryption key from the password
        password = encryption_key.encode()
        salt = b'internet-money-tools-salt'  # Should be random in production
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password))
        self._cipher = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt a string"""
        if not data:
            return data
        
        try:
            encrypted = self._cipher.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt a string"""
        if not encrypted_data:
            return encrypted_data
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise


# Global encryption manager instance
_encryption_manager = EncryptionManager()


def encrypt_token(token: str) -> str:
    """Encrypt a token"""
    return _encryption_manager.encrypt(token)


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a token"""
    return _encryption_manager.decrypt(encrypted_token)