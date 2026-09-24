from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ibvap.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    pool_args = {}
    # SQLite: INTEGER PRIMARY KEY autoincrements, BIGINT does not.
    # Override BigInteger compilation so PKs are INTEGER on SQLite.
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy import BigInteger

    @compiles(BigInteger, "sqlite")
    def _compile_bigint_sqlite(type_, compiler, **kw):
        return "INTEGER"
else:
    pool_args = {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    **pool_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """Context manager for database session (non-FastAPI contexts)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def migrate_alert_status_check(conn, db_path: str) -> bool:
    """SQLite CHECK constraints cannot be ALTERed — rebuild the alerts table
    with an extended status enum. Returns True if a rebuild happened.
    Preserves rows, PK ids (child FKs stay valid), and named indexes.
    Idempotent: no-op when the CHECK already lists 'escalated'.
    Backup is the CALLER's job (see init_db)."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='alerts'"
    ).fetchone()
    if row is None or row[0] is None:
        return False
    old_sql = row[0]
    marker = "('fired', 'enriched', 'acknowledged')"
    if marker not in old_sql:
        return False  # already migrated (or created from the new model)
    new_sql = old_sql.replace(
        marker, "('fired', 'enriched', 'acknowledged', 'escalated', 'false_positive')"
    )
    index_sql = [
        r[0] for r in conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' "
            "AND tbl_name='alerts' AND sql IS NOT NULL"
        ).fetchall()
    ]
    fk_was_off = conn.execute("PRAGMA foreign_keys").fetchone()[0] == 0
    if not fk_was_off:
        conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("BEGIN")
        conn.execute(new_sql.replace("CREATE TABLE alerts", "CREATE TABLE alerts_new", 1))
        conn.execute("INSERT INTO alerts_new SELECT * FROM alerts")
        conn.execute("DROP TABLE alerts")
        conn.execute("ALTER TABLE alerts_new RENAME TO alerts")
        for sql in index_sql:
            conn.execute(sql)
        bad = conn.execute("PRAGMA foreign_key_check").fetchall()
        if bad:
            conn.execute("ROLLBACK")
            raise RuntimeError(f"foreign_key_check failed after rebuild: {bad[:5]}")
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        if not fk_was_off:
            conn.execute("PRAGMA foreign_keys=ON")
    return True


def init_db():
    """Initialize database tables. Called on startup."""
    from fusion_server.db.models import Base as ModelsBase
    ModelsBase.metadata.create_all(bind=engine)
    # Additive migration for pre-existing DBs (additive only, idempotent):
    # alerts.ai_source ('template' | 'llava-local' | 'ollama-local' | NULL).
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE alerts ADD COLUMN ai_source VARCHAR(16)"))
    except Exception:
        pass  # column already exists or DB unreachable at import time
    # alerts.reason_detail / alerts.snapshot_path (additive 2026-09-23, idempotent).
    for _ddl in (
        "ALTER TABLE alerts ADD COLUMN reason_detail TEXT",
        "ALTER TABLE alerts ADD COLUMN snapshot_path VARCHAR(512)",
    ):
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(_ddl))
        except Exception:
            pass  # column already exists
    if DATABASE_URL.startswith("sqlite"):
        # "sqlite:///./ibvap.db" → "./ibvap.db" (works as-is with os.path.isfile)
        db_path = DATABASE_URL.split("sqlite:///", 1)[1]
        if db_path and db_path != ":memory:" and os.path.isfile(db_path):
            bak = db_path + ".bak-status-migration"
            if not os.path.isfile(bak):
                try:
                    import shutil
                    shutil.copy2(db_path, bak)
                except OSError:
                    pass  # best-effort backup — never block startup
            raw = engine.raw_connection()
            try:
                migrate_alert_status_check(raw, db_path=db_path)
                raw.commit()
            except Exception:
                try:
                    raw.rollback()
                except Exception:
                    pass
            finally:
                raw.close()