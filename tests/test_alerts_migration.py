"""SQLite cannot ALTER a CHECK constraint — migrating alerts.status must
rebuild the table, preserve rows + child FK references, and recreate indexes."""
import sqlite3

from fusion_server.db.session import migrate_alert_status_check


OLD_ALERTS_DDL = """
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY,
    alert_id TEXT NOT NULL UNIQUE,
    object_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'fired' CHECK (status IN ('fired', 'enriched', 'acknowledged')),
    threat_score REAL NOT NULL DEFAULT 0.0
)
"""


def _fresh_old_db(tmp_path):
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.execute(OLD_ALERTS_DDL)
    conn.execute("CREATE INDEX idx_alerts_status ON alerts (status)")
    conn.execute("CREATE INDEX idx_alerts_alert_id ON alerts (alert_id)")
    conn.execute(
        "INSERT INTO alerts (alert_id, object_id, camera_id, timestamp, reason, status, threat_score) "
        "VALUES ('a1', 'o1', 'cam1', '2026-09-23T12:00:00', 'roi_intrusion', 'acknowledged', 0.6)"
    )
    conn.execute(
        "CREATE TABLE child (id INTEGER PRIMARY KEY, "
        "alert_ref INTEGER REFERENCES alerts(id))"
    )
    conn.execute("INSERT INTO child (alert_ref) VALUES (1)")
    conn.commit()
    return db_path, conn


def test_rebuild_allows_new_statuses_and_preserves_children(tmp_path):
    db_path, conn = _fresh_old_db(tmp_path)

    # Sanity: the old CHECK really is there
    try:
        conn.execute("UPDATE alerts SET status='escalated'")
        raise AssertionError("precondition failed: old CHECK must reject 'escalated'")
    except sqlite3.IntegrityError:
        pass
    conn.rollback()

    did = migrate_alert_status_check(conn, db_path=str(db_path))
    assert did is True

    conn.execute("UPDATE alerts SET status='escalated'")
    conn.execute(
        "INSERT INTO alerts (alert_id, object_id, camera_id, timestamp, reason, status, threat_score) "
        "VALUES ('a2', 'o1', 'cam1', '2026-09-23T12:01:00', 'roi_intrusion', 'false_positive', 0.5)"
    )
    conn.commit()

    assert conn.execute("SELECT status FROM alerts WHERE alert_id='a1'").fetchone() == ("escalated",)
    assert conn.execute("SELECT COUNT(*) FROM child").fetchone()[0] == 1
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    idx = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='alerts'"
    )]
    assert "idx_alerts_status" in idx and "idx_alerts_alert_id" in idx
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()


def test_migrate_is_idempotent(tmp_path):
    db_path, conn = _fresh_old_db(tmp_path)
    assert migrate_alert_status_check(conn, db_path=str(db_path)) is True
    assert migrate_alert_status_check(conn, db_path=str(db_path)) is False
    conn.close()


def test_new_db_ddl_is_skipped(tmp_path):
    """A DB created from the NEW model (create_all) must not be rebuilt."""
    from sqlalchemy import create_engine
    from fusion_server.db.models import Base
    engine = create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    Base.metadata.create_all(bind=engine)
    raw = engine.raw_connection()
    try:
        assert migrate_alert_status_check(raw, db_path=str(tmp_path / "new.db")) is False
    finally:
        raw.close()
