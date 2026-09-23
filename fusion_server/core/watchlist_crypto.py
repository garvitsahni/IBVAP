"""
Watchlist encryption — Fernet symmetric encryption for embedding vectors.

Key resolution order:
  1. WATCHLIST_ENCRYPTION_KEY env var (explicit ops override)
  2. Key file at project root (.watchlist_key) — persists across restarts;
     created atomically (O_EXCL) with 0600 on first use.
A key generated only into the process environment would make existing
ciphertext undecryptable after a restart.
"""
import os
import json
from pathlib import Path
from typing import List, Union
from cryptography.fernet import Fernet, InvalidToken

# Project root (fusion_server/core/ -> up two levels), independent of cwd.
_KEY_FILE = Path(__file__).resolve().parents[2] / ".watchlist_key"


def get_key() -> bytes:
    """Get the Fernet encryption key (env override, else persistent key file)."""
    key_str = os.environ.get("WATCHLIST_ENCRYPTION_KEY")
    if key_str:
        return key_str.encode()

    if _KEY_FILE.exists():
        key = _KEY_FILE.read_bytes().strip()
        if key:
            return key

    key = Fernet.generate_key()
    try:
        fd = os.open(_KEY_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key)
    except FileExistsError:
        # Lost a creation race — use the winner's key.
        key = _KEY_FILE.read_bytes().strip()
    os.environ["WATCHLIST_ENCRYPTION_KEY"] = key.decode()
    return key


def encrypt_embedding(embedding: List[float], key: bytes) -> bytes:
    """Encrypt embedding vector to bytes."""
    fernet = Fernet(key)
    data = json.dumps(embedding).encode()
    return fernet.encrypt(data)


def decrypt_embedding(encrypted: Union[bytes, str], key: bytes) -> List[float]:
    """Decrypt bytes (or str) back to embedding vector."""
    fernet = Fernet(key)
    data = fernet.decrypt(encrypted)
    return json.loads(data.decode())


def load_embedding(value: Union[bytes, str, list, tuple], key: bytes) -> List[float]:
    """Read a stored watchlist embedding in any form we may encounter:
      - Fernet token (str/bytes)  — current encrypted-at-rest format
      - JSON list string          — legacy plaintext rows written before encryption
      - list/tuple                — in-memory ORM values
    Raises on anything else (Fernet.InvalidToken / json errors) so corruption
    stays visible instead of silently skipping entries.
    """
    if isinstance(value, (list, tuple)):
        return [float(x) for x in value]
    if isinstance(value, str) and value.lstrip().startswith("["):
        return [float(x) for x in json.loads(value)]
    return decrypt_embedding(value, key)
