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
