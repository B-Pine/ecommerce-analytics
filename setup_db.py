from pathlib import Path

from app.db import pg_pool

SQL_DIR = Path(__file__).parent / "sql"

with pg_pool.connection() as conn:
    for filename in ("schema.sql", "seed.sql"):
        conn.execute((SQL_DIR / filename).read_text())
        print(f"Ran {filename}")
