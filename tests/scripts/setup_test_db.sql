-- Setup script for V9 Real Integration Tests
-- Creates required tables in PostgreSQL for testing

-- Drop tables if they exist (for clean state)
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    status VARCHAR(20) DEFAULT '1',
    user_type VARCHAR(20) DEFAULT 'NORMAL',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create orders table
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_no VARCHAR(50) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'pending',
    amount DECIMAL(10, 2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create products table
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) DEFAULT 0.00,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create order_items table (for join tests)
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER DEFAULT 1,
    price DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance testing
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_type ON users(type);
CREATE INDEX idx_users_name ON users(name);
CREATE INDEX idx_users_email ON users(email);

CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_order_no ON orders(order_no);
CREATE INDEX idx_orders_amount ON orders(amount);

CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_order_items_product_id ON order_items(product_id);

CREATE INDEX idx_products_category ON products(category);

-- Insert test data
INSERT INTO users (name, email, status, user_type) VALUES
    ('张三', 'zhangsan@example.com', '1', 'VIP'),
    ('李四', 'lisi@example.com', '1', 'NORMAL'),
    ('王五', 'wangwu@example.com', '0', 'PREMIUM'),
    ('赵六', 'zhaoliu@example.com', '1', 'VIP'),
    ('孙七', 'sunqi@example.com', '1', 'NORMAL'),
    ('周八', 'zhouba@example.com', '0', 'PREMIUM'),
    ('吴九', 'wujiu@example.com', '1', 'VIP'),
    ('郑十', 'zhengshi@example.com', '1', 'NORMAL'),
    ('钱一', 'qianyi@example.com', '0', 'PREMIUM'),
    ('陈二', 'chener@example.com', '1', 'VIP');

INSERT INTO products (name, price, category) VALUES
    ('iPhone 15', 7999.00, 'Electronics'),
    ('MacBook Pro', 19999.00, 'Electronics'),
    ('AirPods Pro', 1999.00, 'Electronics'),
    ('iPad Air', 4999.00, 'Electronics'),
    ('Apple Watch', 2999.00, 'Electronics'),
    ('矿泉水', 2.00, 'Food'),
    ('方便面', 5.00, 'Food'),
    ('火腿肠', 8.00, 'Food'),
    ('笔记本', 15.00, 'Stationery'),
    ('铅笔', 2.00, 'Stationery');

INSERT INTO orders (order_no, user_id, status, amount) VALUES
    ('ORD202401001', 1, 'completed', 9998.00),
    ('ORD202401002', 1, 'pending', 2999.00),
    ('ORD202401003', 2, 'completed', 7999.00),
    ('ORD202401004', 3, 'cancelled', 1999.00),
    ('ORD202401005', 4, 'completed', 4999.00),
    ('ORD202401006', 5, 'processing', 15.00),
    ('ORD202401007', 6, 'completed', 23.00),
    ('ORD202401008', 7, 'pending', 2999.00),
    ('ORD202401009', 8, 'completed', 19999.00),
    ('ORD202401010', 9, 'cancelled', 8.00);

INSERT INTO order_items (order_id, product_id, quantity, price) VALUES
    (1, 1, 1, 7999.00),
    (1, 3, 1, 1999.00),
    (2, 4, 1, 2999.00),
    (3, 1, 1, 7999.00),
    (4, 3, 1, 1999.00),
    (5, 4, 1, 4999.00),
    (6, 9, 1, 15.00),
    (7, 6, 5, 2.00),
    (7, 7, 3, 5.00),
    (8, 5, 1, 2999.00),
    (9, 2, 1, 19999.00),
    (10, 8, 4, 2.00);

-- Verify data
SELECT 'Users:' as info, COUNT(*) as count FROM users
UNION ALL
SELECT 'Orders:', COUNT(*) FROM orders
UNION ALL
SELECT 'Products:', COUNT(*) FROM products
UNION ALL
SELECT 'Order Items:', COUNT(*) FROM order_items;
