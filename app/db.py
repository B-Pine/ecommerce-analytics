import atexit
import os 
import redis

from psycopg_pool import ConnectionPool
from pymongo import MongoClient

pg_pool = ConnectionPool(
    conninfo=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ecommerce"),
    min_size=1,
    max_size=5,
    open=True
)

atexit.register(pg_pool.close)  # close the pool cleanly before python suts down


# Redis: Top 10 cache
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    decode_responses=True,
)

# MongoDB: shopping cart, one document per session
mongo_client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
sessions = mongo_client["ecommerce"]["sessions"]
