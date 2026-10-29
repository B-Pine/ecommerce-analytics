INSERT INTO customers (name, email) VALUES
    ('Amara Okafor', 'amara@example.com'),
    ('Daniel Reyes', 'daniel@example.com'),
    ('Grace Kim',    'grace@example.com'),
    ('Liam Carter',  'liam@example.com');

INSERT INTO products (name, category, price, stock_quantity, metadata) VALUES
    ('Running Shoes',       'Footwear',    89.99, 40, '{"sizes": [40, 41, 42, 43], "colors": ["black", "white"]}'),
    ('Leather Boots',       'Footwear',   149.00, 15, '{"sizes": [41, 42, 44], "colors": ["brown"]}'),
    ('Cotton T-Shirt',      'Clothing',    19.99, 100, '{"sizes": ["S", "M", "L", "XL"], "colors": ["white", "navy", "red"]}'),
    ('Denim Jacket',        'Clothing',    79.50, 25, '{"sizes": ["M", "L"], "colors": ["blue"]}'),
    ('Wireless Earbuds',    'Electronics', 59.99, 60, '{"colors": ["black"], "battery_hours": 24}'),
    ('Smart Watch',         'Electronics', 199.00, 10, '{"colors": ["black", "silver"], "water_resistant": true}'),
    ('Phone Charger',       'Electronics', 15.00, 200, '{"wattage": 20}');

INSERT INTO orders (customer_id, status, created_at) VALUES
    (1, 'delivered', '2026-09-05 10:15'),
    (1, 'shipped',   '2026-10-12 18:40'),
    (2, 'delivered', '2026-09-20 09:05'),
    (2, 'paid',      '2026-10-25 14:30'),
    (3, 'delivered', '2026-10-01 11:00'),
    (3, 'cancelled', '2026-10-03 16:20'),
    (4, 'pending',   '2026-10-27 08:10');

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
    (1, 1, 1,  84.99),
    (1, 3, 3,  19.99),
    (2, 5, 1,  59.99),
    (3, 6, 1, 199.00),
    (3, 7, 2,  15.00),
    (4, 3, 2,  19.99),
    (4, 4, 1,  79.50),
    (5, 1, 1,  89.99),
    (5, 5, 2,  59.99),
    (6, 2, 1, 149.00),
    (7, 7, 1,  15.00);