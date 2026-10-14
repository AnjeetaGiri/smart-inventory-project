import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import database
from app.security import hash_password

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (id SERIAL PRIMARY KEY, name VARCHAR(100) UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS warehouses (id SERIAL PRIMARY KEY, name VARCHAR(120) UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, sku VARCHAR(80) UNIQUE NOT NULL, name VARCHAR(200) NOT NULL, category_id INT NOT NULL REFERENCES categories(id), reorder_level INT NOT NULL DEFAULT 10 CHECK (reorder_level >= 0), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username VARCHAR(80) UNIQUE NOT NULL, password_hash TEXT NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS stock_movements (id BIGSERIAL PRIMARY KEY, product_id INT NOT NULL REFERENCES products(id), warehouse_id INT NOT NULL REFERENCES warehouses(id), quantity INT NOT NULL CHECK (quantity > 0), movement_type VARCHAR(3) NOT NULL CHECK (movement_type IN ('IN','OUT')), note VARCHAR(500), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE INDEX IF NOT EXISTS idx_movements_product_created ON stock_movements(product_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
"""
with database() as conn, conn.cursor() as cur:
    cur.execute(SCHEMA)
    cur.execute("INSERT INTO categories(name) VALUES ('Electronics'),('Office Supplies'),('Networking') ON CONFLICT(name) DO NOTHING")
    cur.execute("INSERT INTO warehouses(name) VALUES ('Mumbai Warehouse'),('Delhi Warehouse') ON CONFLICT(name) DO NOTHING")
    cur.execute("INSERT INTO users(username,password_hash) VALUES (%s,%s) ON CONFLICT(username) DO NOTHING", ('testuser', hash_password('TestPass123!')))
    cur.execute("SELECT id FROM categories WHERE name='Electronics'")
    category_id = cur.fetchone()["id"]
    cur.execute("INSERT INTO products(sku,name,category_id,reorder_level) VALUES ('SKU-1001','Wireless Keyboard',%s,10),('SKU-1002','USB-C Hub',%s,8) ON CONFLICT(sku) DO NOTHING", (category_id, category_id))
    cur.execute("SELECT id FROM warehouses WHERE name='Mumbai Warehouse'")
    warehouse_id = cur.fetchone()["id"]
    cur.execute("SELECT id FROM products WHERE sku='SKU-1001'")
    product_id = cur.fetchone()["id"]
    cur.execute("INSERT INTO stock_movements(product_id,warehouse_id,quantity,movement_type,note) SELECT %s,%s,25,'IN','Initial stock' WHERE NOT EXISTS (SELECT 1 FROM stock_movements WHERE product_id=%s AND note='Initial stock')", (product_id, warehouse_id, product_id))
print('Schema and sample data are ready. Test login: testuser / TestPass123!')
