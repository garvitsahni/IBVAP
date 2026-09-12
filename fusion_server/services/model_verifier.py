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
