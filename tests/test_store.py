from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from app.db import pg_pool, redis_client, sessions
from app.store import (add_product, add_to_cart, checkout, create_order, find_products_by_metadata,
                       get_cart, get_customer_orders, get_revenue_per_customer, get_top_products)

SQL_DIR = Path(__file__).parent.parent / "sql"


@pytest.fixture(autouse=True)
def fresh_data():
    """Reset all three databases before every test."""
    with pg_pool.connection() as conn:
        conn.execute((SQL_DIR / "schema.sql").read_text())
        conn.execute((SQL_DIR / "seed.sql").read_text())
    redis_client.flushdb()
    sessions.delete_many({})


def snapshot():
    """All stock levels plus the number of orders: the state an order can change."""
    with pg_pool.connection() as conn:
        return conn.execute(
            "SELECT array_agg(stock_quantity ORDER BY product_id), (SELECT COUNT(*) FROM orders) "
            "FROM products"
        ).fetchone()


def test_add_product_stores_metadata():
    product_id = add_product("Wool Beanie", "Clothing", 12.50, 30, {"colors": ["grey"]})
    with pg_pool.connection() as conn:
        metadata = conn.execute(
            "SELECT metadata FROM products WHERE product_id = %s", (product_id,)
        ).fetchone()[0]
    assert metadata == {"colors": ["grey"]}


def test_create_order_reserves_stock_and_records_current_price():
    order_id = create_order(4, [(3, 2), (5, 1)])
    with pg_pool.connection() as conn:
        stock = conn.execute(
            "SELECT stock_quantity FROM products WHERE product_id IN (3, 5) ORDER BY product_id"
        ).fetchall()
        prices = conn.execute(
            "SELECT unit_price FROM order_items WHERE order_id = %s ORDER BY product_id", (order_id,)
        ).fetchall()
    assert stock == [(98,), (59,)]
    assert prices == [(Decimal("19.99"),), (Decimal("59.99"),)]


def test_customer_orders_are_newest_first_with_totals():
    order_id = create_order(1, [(3, 2)])
    orders = get_customer_orders(1)
    assert [o["order_id"] for o in orders] == [order_id, 2, 1]
    assert orders[0]["total"] == Decimal("39.98")


def test_unknown_customer_has_no_orders():
    assert get_customer_orders(999) == []


@pytest.mark.parametrize("items, error", [
    ([(6, 50)], ValueError),                          # not enough stock
    ([(999, 1)], ValueError),                         # product does not exist
    ([(3, 1), (6, 50)], ValueError),                  # second item fails after first succeeded
    ([], ValueError),                                 # empty order
    ([(3, -2)], psycopg.errors.CheckViolation),       # negative quantity
    ([(3, 1), (3, 1)], psycopg.errors.UniqueViolation),  # same product twice
])
def test_invalid_order_is_rejected_and_changes_nothing(items, error):
    before = snapshot()
    with pytest.raises(error):
        create_order(1, items)
    assert snapshot() == before


def test_unknown_customer_cannot_order():
    before = snapshot()
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        create_order(999, [(3, 1)])
    assert snapshot() == before

######### second tests, this concerns ranking, cache, metadata, cart

def test_top_products_are_ranked_and_exclude_cancelled_orders():
    top = get_top_products()
    assert [(p["product_id"], p["sales_rank"]) for p in top] == [(3, 1), (5, 2), (7, 2), (1, 4), (4, 5), (6, 5)]
    assert redis_client.ttl("products:top10") > 0


def test_top_products_are_served_from_cache():
    first = get_top_products()
    create_order(4, [(6, 10)])          # would change the ranking...
    assert get_top_products() == first  # ...but the cached list is returned until the TTL expires


def test_revenue_per_customer_excludes_cancelled_orders():
    revenue = {r["name"]: (r["orders"], r["revenue"]) for r in get_revenue_per_customer()}
    assert revenue["Grace Kim"] == (1, Decimal("209.97"))
    assert revenue["Daniel Reyes"] == (2, Decimal("348.48"))


def test_find_products_by_metadata():
    assert [p["product_id"] for p in find_products_by_metadata({"colors": ["black"]})] == [1, 5, 6]


def test_add_to_cart_increments_existing_items():
    add_to_cart("sess-1", 3)
    add_to_cart("sess-1", 3)
    add_to_cart("sess-1", 5, quantity=2)
    items = [(i["product_id"], i["quantity"]) for i in get_cart("sess-1")["items"]]
    assert items == [(3, 2), (5, 2)]


def test_checkout_creates_order_and_removes_cart():
    add_to_cart("sess-1", 3, quantity=2)
    order_id = checkout("sess-1", 4)
    assert get_customer_orders(4)[0]["order_id"] == order_id
    assert get_cart("sess-1") is None


def test_failed_checkout_keeps_the_cart():
    add_to_cart("sess-1", 6, quantity=50)  # only 10 in stock
    with pytest.raises(ValueError):
        checkout("sess-1", 4)
    assert get_cart("sess-1") is not None