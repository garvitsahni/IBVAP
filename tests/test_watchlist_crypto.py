"""Tests for watchlist embedding encryption."""
import pytest
from fusion_server.core.watchlist_crypto import encrypt_embedding, decrypt_embedding, get_key


def test_encrypt_decrypt_round_trip():
    """Encrypt then decrypt returns original embedding."""
    key = get_key()
    embedding = [0.1, 0.2, 0.3, 0.4, 0.5] * 102  # 512 floats
    encrypted = encrypt_embedding(embedding, key)
    decrypted = decrypt_embedding(encrypted, key)
    assert len(decrypted) == len(embedding)
    for a, b in zip(decrypted, embedding):
        assert abs(a - b) < 1e-6


def test_different_embeddings_produce_different_ciphertext():
    """Same key, different embeddings → different ciphertext."""
    key = get_key()
    e1 = encrypt_embedding([0.1] * 512, key)
    e2 = encrypt_embedding([0.2] * 512, key)
    assert e1 != e2


def test_wrong_key_fails_decryption():
    """Wrong key raises exception."""
    from cryptography.fernet import Fernet
    key1 = get_key()
    key2 = Fernet.generate_key()
    encrypted = encrypt_embedding([0.1] * 512, key1)
    with pytest.raises(Exception):
        decrypt_embedding(encrypted, key2)


def test_get_key_generates_if_missing(monkeypatch):
    """get_key generates new key if env var not set."""
    monkeypatch.delenv("WATCHLIST_ENCRYPTION_KEY", raising=False)
    key = get_key()
    assert len(key) > 0
