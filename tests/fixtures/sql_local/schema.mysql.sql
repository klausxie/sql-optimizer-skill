-- Local MySQL 5.6+ test schema for sql-optimize
-- Usage:
--   mysql -h 127.0.0.1 -u root -p sqlopt_test < tests/fixtures/sql_local/schema.mysql.sql
--
-- Notes:
--   1. This script targets MySQL 5.6+ (including 5.7 and 8.0+).
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
  KEY idx_users_status_created (status, created_at)
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
  KEY idx_orders_user_created (user_id, created_at),
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
  KEY idx_shipments_status_shipped (status, shipped_at),
  CONSTRAINT fk_shipments_order_id FOREIGN KEY (order_id) REFERENCES orders(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TEMPORARY TABLE IF EXISTS _sqlopt_digits;
CREATE TEMPORARY TABLE _sqlopt_digits (
  d TINYINT NOT NULL PRIMARY KEY
) ENGINE=MEMORY;

INSERT INTO _sqlopt_digits (d)
VALUES (0), (1), (2), (3), (4), (5), (6), (7), (8), (9);

DROP TEMPORARY TABLE IF EXISTS _sqlopt_seq;
CREATE TEMPORARY TABLE _sqlopt_seq (
  n INT NOT NULL PRIMARY KEY
) ENGINE=MEMORY;

INSERT INTO _sqlopt_seq (n)
SELECT ones.d + tens.d * 10 + hundreds.d * 100 + 1 AS n
FROM _sqlopt_digits AS ones
CROSS JOIN _sqlopt_digits AS tens
CROSS JOIN _sqlopt_digits AS hundreds
WHERE ones.d + tens.d * 10 + hundreds.d * 100 < 360
ORDER BY 1;

-- seed users: medium dataset for stable optimizer behavior
INSERT INTO users (name, email, status, created_at, updated_at)
SELECT
  CONCAT('User', seq.n),
  CONCAT('user', LPAD(CAST(seq.n AS CHAR), 3, '0'), '@example.com'),
  CASE
    WHEN MOD(seq.n, 10) = 0 THEN 'LOCKED'
    WHEN MOD(seq.n, 3) = 0 THEN 'INACTIVE'
    ELSE 'ACTIVE'
  END,
  TIMESTAMPADD(DAY, -MOD(seq.n, 90), CURRENT_TIMESTAMP),
  TIMESTAMPADD(DAY, -MOD(seq.n, 10), CURRENT_TIMESTAMP)
FROM _sqlopt_seq AS seq
WHERE seq.n <= 120
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
SELECT
  MOD(seq.n - 1, 120) + 1,
  CONCAT('ORD-', LPAD(CAST(seq.n AS CHAR), 6, '0')),
  ROUND(10 + MOD(seq.n, 250) * 1.37, 2),
  CASE
    WHEN MOD(seq.n, 11) = 0 THEN 'CANCELLED'
    WHEN MOD(seq.n, 5) = 0 THEN 'SHIPPED'
    WHEN MOD(seq.n, 2) = 0 THEN 'PAID'
    ELSE 'CREATED'
  END,
  TIMESTAMPADD(DAY, -MOD(seq.n, 180), CURRENT_TIMESTAMP)
FROM _sqlopt_seq AS seq
WHERE seq.n <= 360
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
SELECT
  o.id,
  CASE
    WHEN MOD(o.id, 3) = 0 THEN 'UPS'
    WHEN MOD(o.id, 3) = 1 THEN 'DHL'
    ELSE 'FEDEX'
  END,
  CONCAT('TRK-', LPAD(CAST(o.id AS CHAR), 8, '0')),
  CASE
    WHEN o.status = 'CANCELLED' THEN 'CANCELLED'
    WHEN o.status IN ('PAID', 'SHIPPED') THEN 'SHIPPED'
    ELSE 'INIT'
  END,
  CASE
    WHEN o.status IN ('PAID', 'SHIPPED') THEN TIMESTAMPADD(DAY, 1, o.created_at)
    ELSE NULL
  END
FROM (
  SELECT id, status, created_at
  FROM orders
  ORDER BY id
  LIMIT 220
) AS o
LEFT JOIN shipments AS s ON s.order_id = o.id
WHERE s.order_id IS NULL;

DROP TEMPORARY TABLE IF EXISTS _sqlopt_seq;
DROP TEMPORARY TABLE IF EXISTS _sqlopt_digits;
