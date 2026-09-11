"""
Watchlist encryption — Fernet symmetric encryption for embedding vectors.
"""
import os
import json
from typing import List
from cryptography.fernet import Fernet


def get_key() -> bytes:
    """Get or generate Fernet encryption key."""
    key_str = os.environ.get("WATCHLIST_ENCRYPTION_KEY")
    if key_str:
        return key_str.encode()
    # Generate and store new key
    key = Fernet.generate_key()
    os.environ["WATCHLIST_ENCRYPTION_KEY"] = key.decode()
    return key


def encrypt_embedding(embedding: List[float], key: bytes) -> bytes:
    """Encrypt embedding vector to bytes."""
    fernet = Fernet(key)
    data = json.dumps(embedding).encode()
    return fernet.encrypt(data)


def decrypt_embedding(encrypted: bytes, key: bytes) -> List[float]:
    """Decrypt bytes back to embedding vector."""
    fernet = Fernet(key)
    data = fernet.decrypt(encrypted)
    return json.loads(data.decode())
