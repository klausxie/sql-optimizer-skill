-- Local MySQL 8.0+ test schema for sql-optimize
-- Usage:
--   mysql -h 127.0.0.1 -u root -p sqlopt_test < tests/fixtures/sql_local/schema.mysql.sql
--
-- Notes:
--   1. This script targets MySQL 8.0+ only.
--   2. Table creation and seed inserts are idempotent for repeated local runs.
--   3. It assumes the target database already exists and is selected.

CREATE TABLE IF NOT EXISTS users (
  id BIGINT NOT NULL AUTO_INCREMENT,
  name VARCHAR(128) NOT NULL,
  email VARCHAR(255) DEFAULT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_email (email),
  KEY idx_users_name (name),
  KEY idx_users_status_created (status, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orders (
  id BIGINT NOT NULL AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  order_no VARCHAR(64) NOT NULL,
  amount DECIMAL(12, 2) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'CREATED',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_orders_order_no (order_no),
  KEY idx_orders_user_created (user_id, created_at DESC),
  KEY idx_orders_status (status),
  CONSTRAINT fk_orders_user_id FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS shipments (
  id BIGINT NOT NULL AUTO_INCREMENT,
  order_id BIGINT NOT NULL,
  carrier VARCHAR(64) NOT NULL,
  tracking_no VARCHAR(128) DEFAULT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'INIT',
  shipped_at TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (id),
  KEY idx_shipments_order (order_id),
  KEY idx_shipments_status_shipped (status, shipped_at DESC),
  CONSTRAINT fk_shipments_order_id FOREIGN KEY (order_id) REFERENCES orders(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- seed users: medium dataset for stable optimizer behavior
INSERT INTO users (name, email, status, created_at, updated_at)
WITH RECURSIVE seq AS (
  SELECT 1 AS n
  UNION ALL
  SELECT n + 1 FROM seq WHERE n < 120
)
SELECT
  CONCAT('User', n),
  CONCAT('user', LPAD(CAST(n AS CHAR), 3, '0'), '@example.com'),
  CASE
    WHEN MOD(n, 10) = 0 THEN 'LOCKED'
    WHEN MOD(n, 3) = 0 THEN 'INACTIVE'
    ELSE 'ACTIVE'
  END,
  TIMESTAMPADD(DAY, -MOD(n, 90), CURRENT_TIMESTAMP),
  TIMESTAMPADD(DAY, -MOD(n, 10), CURRENT_TIMESTAMP)
FROM seq
ON DUPLICATE KEY UPDATE updated_at = updated_at;

INSERT INTO users (name, email, status)
VALUES
  ('Alice', 'alice@example.com', 'ACTIVE'),
  ('Bob', 'bob@example.com', 'ACTIVE'),
  ('Charlie', 'charlie@example.com', 'INACTIVE'),
  ('David', 'david@example.com', 'ACTIVE'),
  ('Eve', 'eve@example.com', 'LOCKED')
ON DUPLICATE KEY UPDATE updated_at = updated_at;

-- seed orders: around 360 rows
INSERT INTO orders (user_id, order_no, amount, status, created_at)
WITH RECURSIVE seq AS (
  SELECT 1 AS n
  UNION ALL
  SELECT n + 1 FROM seq WHERE n < 360
)
SELECT
  MOD(n - 1, 120) + 1,
  CONCAT('ORD-', LPAD(CAST(n AS CHAR), 6, '0')),
  ROUND(10 + MOD(n, 250) * 1.37, 2),
  CASE
    WHEN MOD(n, 11) = 0 THEN 'CANCELLED'
    WHEN MOD(n, 5) = 0 THEN 'SHIPPED'
    WHEN MOD(n, 2) = 0 THEN 'PAID'
    ELSE 'CREATED'
  END,
  TIMESTAMPADD(DAY, -MOD(n, 180), CURRENT_TIMESTAMP)
FROM seq
ON DUPLICATE KEY UPDATE order_no = order_no;

INSERT INTO orders (user_id, order_no, amount, status, created_at)
SELECT id, 'ORD-1001', 199.00, 'PAID', TIMESTAMPADD(DAY, -4, CURRENT_TIMESTAMP)
FROM users
WHERE email = 'alice@example.com'
ON DUPLICATE KEY UPDATE order_no = order_no;

INSERT INTO orders (user_id, order_no, amount, status, created_at)
SELECT id, 'ORD-1002', 59.90, 'CREATED', TIMESTAMPADD(DAY, -3, CURRENT_TIMESTAMP)
FROM users
WHERE email = 'bob@example.com'
ON DUPLICATE KEY UPDATE order_no = order_no;

INSERT INTO orders (user_id, order_no, amount, status, created_at)
SELECT id, 'ORD-1003', 389.50, 'SHIPPED', TIMESTAMPADD(DAY, -2, CURRENT_TIMESTAMP)
FROM users
WHERE email = 'david@example.com'
ON DUPLICATE KEY UPDATE order_no = order_no;

-- seed shipments: around 220 rows
INSERT INTO shipments (order_id, carrier, tracking_no, status, shipped_at)
WITH picked AS (
  SELECT
    o.id,
    o.status,
    o.created_at,
    ROW_NUMBER() OVER (ORDER BY o.id) AS rn
  FROM orders o
)
SELECT
  p.id,
  CASE
    WHEN MOD(p.id, 3) = 0 THEN 'UPS'
    WHEN MOD(p.id, 3) = 1 THEN 'DHL'
    ELSE 'FEDEX'
  END,
  CONCAT('TRK-', LPAD(CAST(p.id AS CHAR), 8, '0')),
  CASE
    WHEN p.status = 'CANCELLED' THEN 'CANCELLED'
    WHEN p.status IN ('PAID', 'SHIPPED') THEN 'SHIPPED'
    ELSE 'INIT'
  END,
  CASE
    WHEN p.status IN ('PAID', 'SHIPPED') THEN TIMESTAMPADD(DAY, 1, p.created_at)
    ELSE NULL
  END
FROM picked p
LEFT JOIN shipments s ON s.order_id = p.id
WHERE p.rn <= 220
  AND s.order_id IS NULL;
