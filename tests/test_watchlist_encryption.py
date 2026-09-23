"""Watchlist encryption-at-rest (Bug B).

ARCHITECTURE.md: "Watchlist matcher: local encrypted embedding store".
Bugs fixed here:
  - API create stored embeddings in PLAINTEXT while WatchlistMatcher always
    called decrypt_embedding -> every match attempt failed (InvalidToken).
  - get_key() generated a fresh key per process unless WATCHLIST_ENCRYPTION_KEY
    was set, so ciphertext would become undecryptable across restarts.
  - Legacy plaintext rows (pre-encryption data) must still match (honest fallback).
"""
import json

import numpy as np
from sqlalchemy import text

from fusion_server.core.watchlist_crypto import get_key, encrypt_embedding, load_embedding
from fusion_server.db.models import Watchlist
from fusion_server.services.watchlist_matcher import WatchlistMatcher


def _random_unit_vector(dim=512):
    v = np.random.randn(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def test_get_key_stable_across_process_restarts(monkeypatch, tmp_path):
    """Key must survive 'restarts': stored in key file, not only in env."""
    from fusion_server.core import watchlist_crypto
    key_file = tmp_path / ".watchlist_key"
    monkeypatch.setattr(watchlist_crypto, "_KEY_FILE", key_file)
    monkeypatch.delenv("WATCHLIST_ENCRYPTION_KEY", raising=False)

    k1 = watchlist_crypto.get_key()
    # simulate process restart: env gone, file remains
    monkeypatch.delenv("WATCHLIST_ENCRYPTION_KEY", raising=False)
    k2 = watchlist_crypto.get_key()
    assert k1 == k2
    assert key_file.exists()


def test_api_create_stores_encrypted_embedding(client, db_session):
    emb = _random_unit_vector().tolist()
    resp = client.post("/api/v1/watchlist", json={
        "watchlist_type": "face",
        "reference_id": "enc-case-1",
        "embedding": emb,
    })
    assert resp.status_code == 201, resp.text

    stored = db_session.query(Watchlist).filter(
        Watchlist.reference_id == "enc-case-1"
    ).first()
    assert stored is not None
    value = stored.embedding if isinstance(stored.embedding, str) else str(stored.embedding)
    # Fernet tokens are base64url ('.' never appears); a plaintext embedding is a
    # JSON list like "[0.123, ...]".
    assert not value.strip().startswith("["), f"embedding stored in plaintext: {value[:80]}"


def test_api_roundtrip_returns_original_embedding(client):
    emb = _random_unit_vector().tolist()
    resp = client.post("/api/v1/watchlist", json={
        "watchlist_type": "face",
        "reference_id": "enc-case-2",
        "embedding": emb,
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["embedding"] == emb

    got = client.get("/api/v1/watchlist").json()
    row = next(r for r in got if r["reference_id"] == "enc-case-2")
    assert row["embedding"] == emb


def test_matcher_matches_encrypted_entry(client, db_session):
    emb = _random_unit_vector()
    resp = client.post("/api/v1/watchlist", json={
        "watchlist_type": "face",
        "reference_id": "enc-case-3",
        "embedding": emb.tolist(),
    })
    assert resp.status_code == 201, resp.text

    match = WatchlistMatcher().match_detection(db_session, emb, "person")
    assert match is not None, "matcher failed to match an identical encrypted watchlist embedding"
    assert match["reference_id"] == "enc-case-3"
    assert match["similarity"] >= 0.65


def test_matcher_matches_legacy_plaintext_entry(client, db_session):
    """Rows written before encryption existed must still match (fallback, no silent drop)."""
    emb = _random_unit_vector()
    resp = client.post("/api/v1/watchlist", json={
        "watchlist_type": "face",
        "reference_id": "legacy-case-1",
        "embedding": emb.tolist(),
    })
    assert resp.status_code == 201, resp.text

    # Overwrite the stored value with legacy plaintext, bypassing the API.
    row = db_session.query(Watchlist).filter(
        Watchlist.reference_id == "legacy-case-1"
    ).first()
    db_session.execute(
        text("UPDATE watchlist SET embedding = :v WHERE id = :i"),
        {"v": json.dumps(emb.tolist()), "i": row.id},
    )
    db_session.commit()

    match = WatchlistMatcher().match_detection(db_session, emb, "person")
    assert match is not None, "legacy plaintext watchlist entry silently failed to match"
    assert match["reference_id"] == "legacy-case-1"


def test_load_embedding_handles_all_stored_forms():
    key = get_key()
    emb = [0.25, 0.5, 0.75]
    token = encrypt_embedding(emb, key).decode("ascii")
    assert load_embedding(token, key) == emb
    assert load_embedding(json.dumps(emb), key) == emb  # legacy plaintext str
    assert load_embedding(emb, key) == emb              # in-memory list
