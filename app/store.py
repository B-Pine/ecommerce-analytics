from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.db import pg_pool


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