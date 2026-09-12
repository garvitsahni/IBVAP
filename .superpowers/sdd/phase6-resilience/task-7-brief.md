# Task 7: Signed Model Packages + Verification

**Files:**
- Create: `fusion_server/services/model_verifier.py`
- Create: `edge/model_verifier.py`
- Create: `scripts/generate_model_keys.py`
- Create: `scripts/sign_model.py`
- Test: `tests/test_model_verifier.py`

**Interfaces:**
- Consumes: `.pt.signed` file (ZIP with model.pt, metadata.json, signature.bin), public key
- Produces: `ModelVerifier.verify() -> bool`, `ModelVerifier.extract_model() -> str`

## Steps

### Step 1: Install cryptography

Run: `pip install cryptography` (should already be available)

### Step 2: Write the failing tests

```python
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
```

### Step 3: Run tests to verify they fail

Run: `pytest tests/test_model_verifier.py -v`
Expected: FAIL

### Step 4: Implement ModelVerifier (server-side)

Create `fusion_server/services/model_verifier.py`:

```python
"""ModelVerifier — Ed25519 signature + SHA-256 hash verification for model packages."""
import hashlib
import json
import logging
import os
import zipfile
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger(__name__)


class ModelVerifier:
    def verify(self, signed_path: str, public_key_path: str) -> bool:
        if not os.path.exists(signed_path) or not os.path.exists(public_key_path):
            return False
        try:
            with zipfile.ZipFile(signed_path, "r") as zf:
                names = zf.namelist()
                if not all(n in names for n in ("model.pt", "metadata.json", "signature.bin")):
                    logger.error("Signed package missing required files")
                    return False
                model_bytes = zf.read("model.pt")
                metadata_bytes = zf.read("metadata.json")
                signature = zf.read("signature.bin")

            metadata = json.loads(metadata_bytes)
            expected_hash = metadata.get("hash", "")
            actual_hash = hashlib.sha256(model_bytes).hexdigest()
            if actual_hash != expected_hash:
                logger.error(f"Model hash mismatch: expected {expected_hash}, got {actual_hash}")
                return False

            pub_pem = open(public_key_path, "rb").read()
            public_key = serialization.load_pem_public_key(pub_pem)
            public_key.verify(signature, metadata_bytes)
            logger.info(f"Model verified: {signed_path}")
            return True
        except InvalidSignature:
            logger.error(f"Invalid signature: {signed_path}")
            return False
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return False

    def extract_model(self, signed_path: str, public_key_path: str, output_dir: str) -> Optional[str]:
        if not self.verify(signed_path, public_key_path):
            return None
        with zipfile.ZipFile(signed_path, "r") as zf:
            zf.extract("model.pt", output_dir)
        return os.path.join(output_dir, "model.pt")
```

### Step 5: Implement edge model_verifier.py

Create `edge/model_verifier.py`:

```python
"""Edge-side model verification — identical logic to server ModelVerifier."""
from fusion_server.services.model_verifier import ModelVerifier

__all__ = ["ModelVerifier"]
```

### Step 6: Implement key generation script

Create `scripts/generate_model_keys.py`:

```python
#!/usr/bin/env python3
"""Generate Ed25519 keypair for model signing."""
import os
import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "config/model_keys"
    os.makedirs(output_dir, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_path = os.path.join(output_dir, "model_signing.key")
    pub_path = os.path.join(output_dir, "model_signing.pub")

    with open(priv_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(pub_path, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))

    os.chmod(priv_path, 0o600)
    print(f"Keys generated in {output_dir}/")
    print(f"  Private: {priv_path} (keep secret!)")
    print(f"  Public:  {pub_path} (deploy to edge)")


if __name__ == "__main__":
    main()
```

### Step 7: Implement signing script

Create `scripts/sign_model.py`:

```python
#!/usr/bin/env python3
"""Sign a YOLO model file for offline deployment."""
import hashlib
import json
import os
import sys
import zipfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization


def main():
    if len(sys.argv) != 4:
        print("Usage: sign_model.py <model.pt> <private_key> <output.signed>")
        sys.exit(1)

    model_path, key_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]

    model_bytes = open(model_path, "rb").read()
    model_hash = hashlib.sha256(model_bytes).hexdigest()

    metadata = {
        "name": os.path.basename(model_path),
        "version": "1.0",
        "hash": model_hash,
    }
    metadata_bytes = json.dumps(metadata, sort_keys=True).encode()

    private_key = serialization.load_pem_private_key(open(key_path, "rb").read(), password=None)
    signature = private_key.sign(metadata_bytes)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("model.pt", model_bytes)
        zf.writestr("metadata.json", json.dumps(metadata, sort_keys=True))
        zf.writestr("signature.bin", signature)

    print(f"Signed model: {output_path}")
    print(f"  Hash: {model_hash}")


if __name__ == "__main__":
    main()
```

### Step 8: Run tests to verify they pass

Run: `pytest tests/test_model_verifier.py -v`
Expected: 5 passed

### Step 9: Commit

```bash
git add fusion_server/services/model_verifier.py edge/model_verifier.py scripts/generate_model_keys.py scripts/sign_model.py tests/test_model_verifier.py
git commit -m "feat: add Ed25519 model signing and verification"
```
