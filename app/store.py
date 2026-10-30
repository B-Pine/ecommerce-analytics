import json
import logging
from datetime import timezone, datetime

import redis
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.db import pg_pool, redis_client, sessions


TOP_PRODUCTS_KEY = "products:top10"
TOP_PRODUCTS_TTL_SECONDS = 600

def add_product(name, category, price, stock_quantity, metadata=None):
    """Insert a product and return its new id."""
    with pg_pool.connection() as conn:
        return conn.execute(
            "INSERT INTO products (name, category, price, stock_quantity, metadata) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING product_id",
            (name, category, price, stock_quantity, Jsonb(metadata or {})),
        ).fetchone()[0]


def create_order(customer_id, items):
    """Create an order atomically. items: list of (product_id, quantity) pairs."""
    if not items:
        raise ValueError("An order needs at least one item")

    with pg_pool.connection() as conn:
        order_id = conn.execute(
            "INSERT INTO orders (customer_id) VALUES (%s) RETURNING order_id",
            (customer_id,),
        ).fetchone()[0]

        for product_id, quantity in items:
            # Reserve stock and read the current price in one atomic statement
            row = conn.execute(
                "UPDATE products SET stock_quantity = stock_quantity - %s "
                "WHERE product_id = %s AND stock_quantity >= %s RETURNING price",
                (quantity, product_id, quantity),
            ).fetchone()
            if row is None:
                raise ValueError(f"Product {product_id} not found or out of stock")

            conn.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) "
                "VALUES (%s, %s, %s, %s)",
                (order_id, product_id, quantity, row[0]),
            )
    return order_id


def get_customer_orders(customer_id):
    """Return a customer's orders, newest first, with computed totals."""
    with pg_pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        return cur.execute(
            """
            SELECT o.order_id, o.status, o.created_at,
                   SUM(oi.quantity * oi.unit_price) AS total
            FROM orders o
            JOIN order_items oi USING (order_id)
            WHERE o.customer_id = %s
            GROUP BY o.order_id
            ORDER BY o.created_at DESC
            """,
            (customer_id,),
        ).fetchall()


def get_top_products():
    """Top 10 best selling products by units sold, cached in Redis (cache-aside)."""
    try:
        cached = redis_client.get(TOP_PRODUCTS_KEY)
        if cached:
            return json.loads(cached)
    except redis.RedisError as e:
        logging.warning("Redis unavailable, reading from PostgreSQL: %s", e)

    with pg_pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        top = cur.execute(
            """
            WITH sales AS (
                SELECT p.product_id, p.name, p.category, SUM(oi.quantity) AS units_sold
                FROM order_items oi
                JOIN orders o USING (order_id)
                JOIN products p USING (product_id)
                WHERE o.status <> 'cancelled'
                GROUP BY p.product_id
            ),
            ranked AS (
                SELECT *, RANK() OVER (ORDER BY units_sold DESC) AS sales_rank
                FROM sales
            )
            SELECT * FROM ranked
            WHERE sales_rank <= 10
            ORDER BY sales_rank, product_id
            """
        ).fetchall()

    try:
        redis_client.set(TOP_PRODUCTS_KEY, json.dumps(top), ex=TOP_PRODUCTS_TTL_SECONDS)
    except redis.RedisError as e:
        logging.warning("Top proucts not cached: %s", e)
    return top


def get_revenue_per_customer():
    """Revenue and order count per customer, excluding cancelled orders."""
    with pg_pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        return cur.execute(
            """
            WITH order_totals AS (
                SELECT o.order_id, o.customer_id, SUM(oi.quantity * oi.unit_price) AS order_total
                FROM orders o
                JOIN order_items oi USING (order_id)
                WHERE o.status <> 'cancelled'
                GROUP BY o.order_id
            )
            SELECT c.customer_id, c.name,
                   COUNT(ot.order_id) AS orders,
                   COALESCE(SUM(ot.order_total), 0) AS revenue
            FROM customers c
            LEFT JOIN order_totals ot USING (customer_id)
            GROUP BY c.customer_id
            ORDER BY revenue DESC
            """
        ).fetchall()


def find_products_by_metadata(criteria):
    """Products whose metadata contains the given JOSN, e.g.: {"color": ["black"]}."""
    with pg_pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        return cur.execute(
            "SELECT product_id, name, metadata FROM products WHERE metadata @> %s ORDER BY product_id;",
            (Jsonb(criteria),),
        ).fetchall()


def add_to_cart(session_id, product_id, quantity=1):
    """Add a product to a session's cart, creating it if needed."""
    now = datetime.now(timezone.utc)
    # Product already in cart increase it's quantity.
    result = sessions.update_one(
        {"session_id": session_id, "items.product_id": product_id},
        {"$inc": {"items.$.quantity": quantity}, "$set": {"updated_at": now}},
    )

    # Otherwise: append it (upsert create it if it doesn't exists.)
    if result.matched_count == 0:
        sessions.update_one(
            {"session_id": session_id},
            {"$push": {"items": {"product_id": product_id, "quantity": quantity}},
             "$set": {"update_at": now}},
             upsert=True
        )

def get_cart(session_id):
    """Return the cart document, otherwise None."""
    return sessions.find_one({"session_id": session_id}, {"_id": 0})


def checkout(session_id, customer_id):
    """Turn cart into an order in PostgreSQL, then delete a cart."""
    cart = get_cart(session_id=session_id)
    if cart is None:
        raise ValueError(f"There is no cart for session {session_id}")

    order_id = create_order(customer_id, [(itm["product_id"], itm["quantity"]) for itm in cart["items"]])
    sessions.delete_one({"session_id": session_id})
    return order_id