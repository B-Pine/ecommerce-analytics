-- Run: docker compose exec -T postgres psql -U postgres -d ecommerce < sql/queries.sql
-- Reset: python setup_db.py

-- 1. Large dataset
INSERT INTO customers (name, email)
SELECT 'Customer ' || n, 'customer' || n || '@example.com'
FROM generate_series(1, 50000) AS n;

INSERT INTO orders (customer_id, status, created_at)
SELECT 5 + (n % 50000), 'delivered', TIMESTAMPTZ '2026-01-01' + n * INTERVAL '30 seconds'
FROM generate_series(1, 500000) AS n;

INSERT INTO order_items (order_id, product_id, quantity, unit_price)
SELECT order_id, 1 + (order_id % 7), 1, 10.00
FROM orders
WHERE order_id > 7;

INSERT INTO products (name, category, price, stock_quantity, metadata)
SELECT 'Bulk product ' || n, 'Bulk', 10.00, 100,
       jsonb_build_object(
           'colors', jsonb_build_array(
               CASE WHEN n % 1000 = 0 THEN 'gold'
                    ELSE (ARRAY['black', 'white', 'red', 'blue'])[1 + n % 4] END),
           'sizes', jsonb_build_array('S', 'M', 'L'))
FROM generate_series(1, 100000) AS n;

ANALYZE;

-- 2. BEFORE: no indexes
DROP INDEX IF EXISTS idx_orders_customer_id;
DROP INDEX IF EXISTS idx_products_metadata;

EXPLAIN ANALYZE
SELECT o.order_id, o.status, o.created_at, SUM(oi.quantity * oi.unit_price) AS total
FROM orders o
JOIN order_items oi USING (order_id)
WHERE o.customer_id = 25000
GROUP BY o.order_id
ORDER BY o.created_at DESC;

EXPLAIN ANALYZE
SELECT product_id, name, metadata
FROM products
WHERE metadata @> '{"colors": ["gold"]}';

-- 3. Add the indexes
CREATE INDEX idx_orders_customer_id ON orders (customer_id);
CREATE INDEX idx_products_metadata ON products USING GIN (metadata);
ANALYZE orders;
ANALYZE products;

-- 4. AFTER: identical queries
EXPLAIN ANALYZE
SELECT o.order_id, o.status, o.created_at, SUM(oi.quantity * oi.unit_price) AS total
FROM orders o
JOIN order_items oi USING (order_id)
WHERE o.customer_id = 25000
GROUP BY o.order_id
ORDER BY o.created_at DESC;

EXPLAIN ANALYZE
SELECT product_id, name, metadata
FROM products
WHERE metadata @> '{"colors": ["gold"]}';