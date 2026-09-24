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