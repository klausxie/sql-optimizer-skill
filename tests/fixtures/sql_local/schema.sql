-- Local PostgreSQL test schema for sql-optimize
-- Usage:
--   psql -h 127.0.0.1 -U postgres -d sqlopt_test -f tests/fixtures/sql_local/schema.sql

BEGIN;

CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  email VARCHAR(255) UNIQUE,
  status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  order_no VARCHAR(64) NOT NULL UNIQUE,
  amount NUMERIC(12, 2) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'CREATED',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shipments (
  id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL REFERENCES orders(id),
  carrier VARCHAR(64) NOT NULL,
  tracking_no VARCHAR(128),
  status VARCHAR(32) NOT NULL DEFAULT 'INIT',
  shipped_at TIMESTAMPTZ
);

-- indexes used by optimizer evidence collection and common predicates
CREATE INDEX IF NOT EXISTS idx_users_name ON users(name);
CREATE INDEX IF NOT EXISTS idx_users_status_created ON users(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_shipments_order ON shipments(order_id);
CREATE INDEX IF NOT EXISTS idx_shipments_status_shipped ON shipments(status, shipped_at DESC);

-- seed users: medium dataset for stable planner behavior
INSERT INTO users (name, email, status, created_at, updated_at)
SELECT
  'User' || g::text,
  format('user%03s@example.com', g),
  CASE
    WHEN g % 10 = 0 THEN 'LOCKED'
    WHEN g % 3 = 0 THEN 'INACTIVE'
    ELSE 'ACTIVE'
  END,
  NOW() - ((g % 90)::text || ' days')::interval,
  NOW() - ((g % 10)::text || ' days')::interval
FROM generate_series(1, 120) AS g
ON CONFLICT (email) DO NOTHING;

INSERT INTO users (name, email, status)
VALUES
  ('Alice', 'alice@example.com', 'ACTIVE'),
  ('Bob', 'bob@example.com', 'ACTIVE'),
  ('Charlie', 'charlie@example.com', 'INACTIVE'),
  ('David', 'david@example.com', 'ACTIVE'),
  ('Eve', 'eve@example.com', 'LOCKED')
ON CONFLICT (email) DO NOTHING;

-- seed orders: around 360 rows
INSERT INTO orders (user_id, order_no, amount, status, created_at)
SELECT
  ((g - 1) % 120) + 1,
  format('ORD-%06s', g),
  round((10 + (g % 250) * 1.37)::numeric, 2),
  CASE
    WHEN g % 11 = 0 THEN 'CANCELLED'
    WHEN g % 5 = 0 THEN 'SHIPPED'
    WHEN g % 2 = 0 THEN 'PAID'
    ELSE 'CREATED'
  END,
  NOW() - ((g % 180)::text || ' days')::interval
FROM generate_series(1, 360) AS g
ON CONFLICT (order_no) DO NOTHING;

INSERT INTO orders (user_id, order_no, amount, status, created_at)
SELECT id, 'ORD-1001', 199.00, 'PAID', NOW() - INTERVAL '4 days'
FROM users WHERE email = 'alice@example.com'
ON CONFLICT (order_no) DO NOTHING;

INSERT INTO orders (user_id, order_no, amount, status, created_at)
SELECT id, 'ORD-1002', 59.90, 'CREATED', NOW() - INTERVAL '3 days'
FROM users WHERE email = 'bob@example.com'
ON CONFLICT (order_no) DO NOTHING;

INSERT INTO orders (user_id, order_no, amount, status, created_at)
SELECT id, 'ORD-1003', 389.50, 'SHIPPED', NOW() - INTERVAL '2 days'
FROM users WHERE email = 'david@example.com'
ON CONFLICT (order_no) DO NOTHING;

-- seed shipments: around 220 rows
WITH picked AS (
  SELECT
    o.id,
    o.status,
    o.created_at,
    row_number() OVER (ORDER BY o.id) AS rn
  FROM orders o
)
INSERT INTO shipments (order_id, carrier, tracking_no, status, shipped_at)
SELECT
  p.id,
  CASE
    WHEN p.id % 3 = 0 THEN 'UPS'
    WHEN p.id % 3 = 1 THEN 'DHL'
    ELSE 'FEDEX'
  END,
  'TRK-' || LPAD(p.id::text, 8, '0'),
  CASE
    WHEN p.status = 'CANCELLED' THEN 'CANCELLED'
    WHEN p.status IN ('PAID', 'SHIPPED') THEN 'SHIPPED'
    ELSE 'INIT'
  END,
  CASE
    WHEN p.status IN ('PAID', 'SHIPPED') THEN p.created_at + INTERVAL '1 day'
    ELSE NULL
  END
FROM picked p
WHERE p.rn <= 220
  AND NOT EXISTS (SELECT 1 FROM shipments s WHERE s.order_id = p.id);

COMMIT;
