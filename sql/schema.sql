DROP TABLE IF EXISTS order_items, orders, products, customers;

CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY, -- Here the SERIAL act as rawint, it autogenerate the next id if not provided.
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(255) NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE products (
    product_id     SERIAL PRIMARY KEY,
    name           VARCHAR(150)  NOT NULL,
    category       VARCHAR(50)   NOT NULL,
    price          NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    stock_quantity INT           NOT NULL CHECK (stock_quantity >= 0),
    metadata       JSONB         NOT NULL DEFAULT '{}'  -- store json data into decomposed binary format.
);

CREATE TABLE orders (
    order_id    SERIAL PRIMARY KEY,
    customer_id INT         NOT NULL REFERENCES customers(customer_id),
    status      VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'paid', 'shipped', 'delivered', 'cancelled')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE order_items (
    order_id   INT           NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id INT           NOT NULL REFERENCES products(product_id),
    quantity   INT           NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10,2) NOT NULL CHECK (unit_price >= 0),
    PRIMARY KEY (order_id, product_id)
);