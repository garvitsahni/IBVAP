import hashlib
from typing import Optional


def compute_hash(data: str) -> str:
    """Compute SHA-256 hash of input data. Returns hex string."""
    return hashlib.sha256(data.encode()).hexdigest()


def verify_chain(entries: list) -> tuple[bool, Optional[int]]:
    """
    Verify hash chain integrity.
    Returns (is_valid, first_broken_index).
    """
    if not entries:
        return True, None

    for i, entry in enumerate(entries):
        # Verify current hash matches computed hash
        expected_data = f"{entry['object_id']}{entry['camera_id']}{entry['timestamp']}{entry['event_type']}"
        expected_hash = compute_hash(expected_data + "footprint")
        if entry['hash'] != expected_hash:
            return False, i

        # Verify previous_hash linkage
        if i == 0:
            if entry['previous_hash'] is not None:
                return False, i
        else:
            if entry['previous_hash'] != entries[i - 1]['hash']:
                return False, i

    return True, None


def append_entry(object_id: str, camera_id: str, timestamp: str, event_type: str, previous_hash: Optional[str]) -> dict:
    """Create a new footprint entry with proper hash chain linkage."""
    data = f"{object_id}{camera_id}{timestamp}{event_type}"
    hash_value = compute_hash(data + "footprint")
    return {
        "object_id": object_id,
        "camera_id": camera_id,
        "timestamp": timestamp,
        "event_type": event_type,
        "hash": hash_value,
        "previous_hash": previous_hash,
    }