"""Fernet encryption helpers for AI API keys."""

import base64
import hashlib

from cryptography.fernet import Fernet


def _fernet(secret: str) -> Fernet:
    """Derive a Fernet key from the PERFSAGE_SECRET env var."""
    key_bytes = hashlib.sha256(secret.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_key(plaintext: str, secret: str) -> str:
    """Encrypt a plaintext API key. Returns base64-encoded ciphertext."""
    return _fernet(secret).encrypt(plaintext.encode()).decode()


def decrypt_key(ciphertext: str, secret: str) -> str:
    """Decrypt a previously encrypted API key."""
    return _fernet(secret).decrypt(ciphertext.encode()).decode()
