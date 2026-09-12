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
