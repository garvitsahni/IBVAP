from fusion_server.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    rows = conn.execute(text(
        "SELECT conname, pg_get_constraintdef(oid) "
        "FROM pg_constraint "
        "WHERE conrelid = 'public.watchlist'::regclass AND contype = 'c'"
    ))
    for row in rows:
        print(f"{row[0]}: {row[1]}")
