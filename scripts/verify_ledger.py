#!/usr/bin/env python3
"""
Verify ledger integrity - checks hash chain for tampering.
Can be run standalone or as part of test suite.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from fusion_server.db.session import SessionLocal
from fusion_server.db.models import FootprintEntry
from fusion_server.core.ledger import verify_chain, compute_hash


def verify_all_chains(db: Session) -> dict:
    """Verify all footprint chains in the database."""
    # Get all unique object_ids
    object_ids = db.query(FootprintEntry.object_id).distinct().all()
    object_ids = [oid[0] for oid in object_ids]

    results = {
        "total_chains": len(object_ids),
        "valid_chains": 0,
        "broken_chains": 0,
        "details": [],
    }

    for obj_id in object_ids:
        entries = (
            db.query(FootprintEntry)
            .filter(FootprintEntry.object_id == obj_id)
            .order_by(FootprintEntry.timestamp.asc())
            .all()
        )

        chain_data = [
            {
                "object_id": e.object_id,
                "camera_id": e.camera_id,
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type,
                "hash": e.hash,
                "previous_hash": e.previous_hash,
            }
            for e in entries
        ]

        is_valid, broken_idx = verify_chain(chain_data)

        detail = {
            "object_id": obj_id,
            "total_entries": len(entries),
            "is_valid": is_valid,
            "first_seen": entries[0].timestamp.isoformat() if entries else None,
            "last_seen": entries[-1].timestamp.isoformat() if entries else None,
        }

        if not is_valid:
            detail["broken_at_index"] = broken_idx
            detail["broken_entry"] = chain_data[broken_idx] if broken_idx is not None and broken_idx < len(chain_data) else None
            results["broken_chains"] += 1
        else:
            results["valid_chains"] += 1

        results["details"].append(detail)

    return results


def verify_specific_chain(db: Session, object_id: str) -> dict:
    """Verify a specific footprint chain."""
    entries = (
        db.query(FootprintEntry)
        .filter(FootprintEntry.object_id == object_id)
        .order_by(FootprintEntry.timestamp.asc())
        .all()
    )

    if not entries:
        return {"object_id": object_id, "error": "Chain not found", "is_valid": False}

    chain_data = [
        {
            "object_id": e.object_id,
            "camera_id": e.camera_id,
            "timestamp": e.timestamp.isoformat(),
            "event_type": e.event_type,
            "hash": e.hash,
            "previous_hash": e.previous_hash,
        }
        for e in entries
    ]

    is_valid, broken_idx = verify_chain(chain_data)

    result = {
        "object_id": object_id,
        "total_entries": len(entries),
        "is_valid": is_valid,
        "entries": chain_data,
    }

    if not is_valid:
        result["broken_at_index"] = broken_idx
        result["broken_entry"] = chain_data[broken_idx] if broken_idx is not None and broken_idx < len(chain_data) else None

    return result


def test_tamper_detection():
    """Test that tampering is detected."""
    print("Testing tamper detection...")

    # Create a valid chain
    chain = [
        {"object_id": "test_obj", "camera_id": "cam1", "timestamp": "2024-01-01T00:00:00", "event_type": "first_seen", "hash": "", "previous_hash": None},
        {"object_id": "test_obj", "camera_id": "cam2", "timestamp": "2024-01-01T00:05:00", "event_type": "hop", "hash": "", "previous_hash": None},
        {"object_id": "test_obj", "camera_id": "cam3", "timestamp": "2024-01-01T00:10:00", "event_type": "alert", "hash": "", "previous_hash": None},
    ]

    # Compute correct hashes
    for i, entry in enumerate(chain):
        data = f"{entry['object_id']}{entry['camera_id']}{entry['timestamp']}{entry['event_type']}"
        entry['hash'] = compute_hash(data + "footprint")
        if i > 0:
            entry['previous_hash'] = chain[i-1]['hash']

    # Verify valid chain
    is_valid, _ = verify_chain(chain)
    assert is_valid, "Valid chain should pass verification"
    print("✓ Valid chain passes verification")

    # Tamper with middle entry
    chain[1]['camera_id'] = 'cam99'  # Change camera_id

    # Verify tampered chain fails
    is_valid, broken_idx = verify_chain(chain)
    assert not is_valid, "Tampered chain should fail verification"
    assert broken_idx == 1, "Should detect tampering at index 1"
    print("✓ Tampered chain correctly fails verification")

    # Test previous_hash tampering
    chain2 = [
        {"object_id": "test_obj", "camera_id": "cam1", "timestamp": "2024-01-01T00:00:00", "event_type": "first_seen", "hash": "", "previous_hash": None},
        {"object_id": "test_obj", "camera_id": "cam2", "timestamp": "2024-01-01T00:05:00", "event_type": "hop", "hash": "", "previous_hash": None},
    ]
    for i, entry in enumerate(chain2):
        data = f"{entry['object_id']}{entry['camera_id']}{entry['timestamp']}{entry['event_type']}"
        entry['hash'] = compute_hash(data + "footprint")
        if i > 0:
            entry['previous_hash'] = chain2[i-1]['hash']

    # Tamper previous_hash
    chain2[1]['previous_hash'] = 'tampered_hash'

    is_valid, broken_idx = verify_chain(chain2)
    assert not is_valid, "Chain with tampered previous_hash should fail"
    print("✓ Tampered previous_hash correctly detected")

    print("\nAll tamper detection tests passed!")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Verify IBVAP ledger integrity")
    parser.add_argument("--object-id", help="Verify specific object ID")
    parser.add_argument("--test-tamper", action="store_true", help="Run tamper detection tests")
    parser.add_argument("--all", action="store_true", help="Verify all chains (default)")
    args = parser.parse_args()

    if args.test_tamper:
        test_tamper_detection()
        return

    db = SessionLocal()
    try:
        if args.object_id:
            result = verify_specific_chain(db, args.object_id)
            print(f"Object: {result['object_id']}")
            print(f"Valid: {result['is_valid']}")
            print(f"Entries: {result.get('total_entries', 0)}")
            if not result['is_valid'] and 'broken_at_index' in result:
                print(f"BROKEN at index {result['broken_at_index']}: {result['broken_entry']}")
        else:
            results = verify_all_chains(db)
            print(f"Total chains: {results['total_chains']}")
            print(f"Valid: {results['valid_chains']}")
            print(f"Broken: {results['broken_chains']}")
            print()
            for detail in results['details']:
                status = "✓" if detail['is_valid'] else "✗ BROKEN"
                print(f"  {status} {detail['object_id']} ({detail['total_entries']} entries)")
                if not detail['is_valid']:
                    print(f"    Broken at index {detail.get('broken_at_index')}")

            if results['broken_chains'] > 0:
                sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()