"""Tests for ModelVerifier — Ed25519 signature + hash verification."""
import pytest
import os
import json
import hashlib
import zipfile
import tempfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from fusion_server.services.model_verifier import ModelVerifier


@pytest.fixture
def keypair():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv_pem, pub_pem


@pytest.fixture
def signed_model(tmp_path, keypair):
    priv_pem, pub_pem = keypair
    model_content = b"fake model weights"
    model_hash = hashlib.sha256(model_content).hexdigest()
    metadata = {"name": "test_model", "version": "1.0", "hash": model_hash}
    metadata_bytes = json.dumps(metadata, sort_keys=True).encode()

    private_key = serialization.load_pem_private_key(priv_pem, password=None)
    signature = private_key.sign(metadata_bytes)

    model_path = tmp_path / "model.pt"
    model_path.write_bytes(model_content)
    meta_path = tmp_path / "metadata.json"
    meta_path.write_text(json.dumps(metadata, sort_keys=True))
    sig_path = tmp_path / "signature.bin"
    sig_path.write_bytes(signature)

    signed_path = tmp_path / "model.pt.signed"
    with zipfile.ZipFile(signed_path, "w") as zf:
        zf.write(model_path, "model.pt")
        zf.write(meta_path, "metadata.json")
        zf.write(sig_path, "signature.bin")

    pub_key_path = tmp_path / "model_signing.pub"
    pub_key_path.write_bytes(pub_pem)

    return str(signed_path), str(pub_key_path)


def test_verify_valid_signature(signed_model):
    """Valid signature returns True."""
    signed_path, pub_key_path = signed_model
    verifier = ModelVerifier()
    assert verifier.verify(signed_path, pub_key_path) is True


def test_verify_corrupted_model(tmp_path, keypair):
    """Corrupted model (hash mismatch) returns False."""
    priv_pem, pub_pem = keypair
    model_content = b"original model"
    model_hash = hashlib.sha256(model_content).hexdigest()
    metadata = {"name": "test", "version": "1.0", "hash": model_hash}
    metadata_bytes = json.dumps(metadata, sort_keys=True).encode()
    private_key = serialization.load_pem_private_key(priv_pem, password=None)
    signature = private_key.sign(metadata_bytes)

    corrupted_content = b"CORRUPTED"
    signed_path = tmp_path / "bad.signed"
    with zipfile.ZipFile(signed_path, "w") as zf:
        zf.writestr("model.pt", corrupted_content)
        zf.writestr("metadata.json", json.dumps(metadata, sort_keys=True))
        zf.writestr("signature.bin", signature)

    pub_key_path = tmp_path / "key.pub"
    pub_key_path.write_bytes(pub_pem)

    verifier = ModelVerifier()
    assert verifier.verify(str(signed_path), str(pub_key_path)) is False


def test_verify_tampered_signature(tmp_path, keypair):
    """Tampered signature returns False."""
    priv_pem, pub_pem = keypair
    model_content = b"model data"
    model_hash = hashlib.sha256(model_content).hexdigest()
    metadata = {"name": "test", "version": "1.0", "hash": model_hash}

    signed_path = tmp_path / "bad.signed"
    with zipfile.ZipFile(signed_path, "w") as zf:
        zf.writestr("model.pt", model_content)
        zf.writestr("metadata.json", json.dumps(metadata, sort_keys=True))
        zf.writestr("signature.bin", b"tampered_signature_bytes")

    pub_key_path = tmp_path / "key.pub"
    pub_key_path.write_bytes(pub_pem)

    verifier = ModelVerifier()
    assert verifier.verify(str(signed_path), str(pub_key_path)) is False


def test_extract_model(signed_model):
    """extract_model writes model.pt to output path and returns it."""
    signed_path, pub_key_path = signed_model
    verifier = ModelVerifier()
    with tempfile.TemporaryDirectory() as out:
        result = verifier.extract_model(signed_path, pub_key_path, out)
        assert os.path.exists(result)
        assert result.endswith("model.pt")


def test_verify_nonexistent_file():
    """verify returns False for missing file."""
    verifier = ModelVerifier()
    assert verifier.verify("/nonexistent.signed", "/nonexistent.pub") is False
