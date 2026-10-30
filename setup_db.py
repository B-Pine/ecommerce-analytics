from pathlib import Path

from app.db import pg_pool, sessions

SQL_DIR = Path(__file__).parent / "sql"

with pg_pool.connection() as conn:
    for filename in ("schema.sql", "seed.sql"):
        conn.execute((SQL_DIR / filename).read_text())
        print(f"Ran {filename}")

# MongoDb deletes cart automatically 7 days after their last update
sessions.create_index("updated_at", expireAfterSeconds=7 * 24 * 3600)
