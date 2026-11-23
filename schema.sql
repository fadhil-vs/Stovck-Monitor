-- ============================================================
-- Stock Monitor — Simple Database Schema
-- Run this in your Supabase SQL Editor.
-- ============================================================

-- Clean up any previous tables
DROP TABLE IF EXISTS stock_movements CASCADE;
DROP TABLE IF EXISTS bill_items CASCADE;
DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS bills CASCADE;
DROP TABLE IF EXISTS items CASCADE;
DROP TABLE IF EXISTS counters CASCADE;
DROP TABLE IF EXISTS stock_orders CASCADE;
DROP TABLE IF EXISTS stock CASCADE;
DROP TABLE IF EXISTS sales CASCADE;

-- 1. Current Stock Table
CREATE TABLE IF NOT EXISTS stock (
    id           BIGSERIAL PRIMARY KEY,
    product_name TEXT UNIQUE NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 0,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Stock Adding Orders (Purchase/Addition history)
CREATE TABLE IF NOT EXISTS stock_orders (
    id           BIGSERIAL PRIMARY KEY,
    order_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    product_name TEXT NOT NULL,
    qty_added    INTEGER NOT NULL DEFAULT 0,
    note         TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Sales Table
-- status: 'unpaid' | 'paid' | 'other' (Not Dealing / Handled by Other)
CREATE TABLE IF NOT EXISTS sales (
    id            BIGSERIAL PRIMARY KEY,
    sl_no         INTEGER NOT NULL,
    bill_no       TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    product_name  TEXT NOT NULL,
    qty           INTEGER NOT NULL DEFAULT 1,
    amount        NUMERIC(12, 2) NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'unpaid',
    sale_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enable Row Level Security (bypassed by service_role key on backend)
ALTER TABLE stock        ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales        ENABLE ROW LEVEL SECURITY;
