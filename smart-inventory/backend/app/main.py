from typing import Literal
import jwt
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from .config import CORS_ORIGINS, JWT_SECRET
from .db import database
from .schemas import LoginRequest, RefreshRequest, MovementRequest
from .security import verify_password, token_pair, create_token, current_user
from datetime import timedelta

app = FastAPI(title="Smart Inventory API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/token")
def login(body: LoginRequest):
    with database() as conn, conn.cursor() as cur:
        cur.execute("SELECT username, password_hash FROM users WHERE username = %s AND is_active = TRUE", (body.username,))
        user = cur.fetchone()
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return token_pair(user["username"])


@app.post("/api/auth/refresh")
def refresh(body: RefreshRequest):
    try:
        payload = jwt.decode(body.refresh_token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Refresh token required")
        username = payload["sub"]
    except (jwt.InvalidTokenError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token") from None
    return token_pair(username)


@app.get("/api/products")
def list_products(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100), sort: str = "name", order: Literal["asc", "desc"] = "asc"
):
    allowed_sort = {"sku": "p.sku", "name": "p.name", "category": "c.name", "reorder_level": "p.reorder_level"}
    if sort not in allowed_sort:
        raise HTTPException(status_code=400, detail="Unsupported sort field")
    direction = "DESC" if order == "desc" else "ASC"
    pattern = f"%{search}%"
    with database() as conn, conn.cursor() as cur:
        cur.execute("""SELECT COUNT(*) AS total FROM products p JOIN categories c ON c.id=p.category_id
                       WHERE p.sku ILIKE %s OR p.name ILIKE %s OR c.name ILIKE %s""", (pattern, pattern, pattern))
        total = cur.fetchone()["total"]
        cur.execute(f"""SELECT p.id, p.sku, p.name, c.name AS category, p.reorder_level,
                         COALESCE(SUM(CASE WHEN sm.movement_type='IN' THEN sm.quantity ELSE -sm.quantity END),0)::int AS current_stock
                         FROM products p JOIN categories c ON c.id=p.category_id
                         LEFT JOIN stock_movements sm ON sm.product_id=p.id
                         WHERE p.sku ILIKE %s OR p.name ILIKE %s OR c.name ILIKE %s
                         GROUP BY p.id, c.name ORDER BY {allowed_sort[sort]} {direction}, p.id
                         LIMIT %s OFFSET %s""", (pattern, pattern, pattern, page_size, (page - 1) * page_size))
        rows = cur.fetchall()
    for row in rows:
        row["status"] = "CRITICAL" if row["current_stock"] <= 0 else "LOW" if row["current_stock"] < row["reorder_level"] else "OK"
    return {"items": rows, "page": page, "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size}


@app.get("/api/products/{product_id}/stock")
def product_stock(product_id: int):
    with database() as conn, conn.cursor() as cur:
        cur.execute("""SELECT w.id AS warehouse_id, w.name AS warehouse,
                       COALESCE(SUM(CASE WHEN sm.movement_type='IN' THEN sm.quantity ELSE -sm.quantity END),0)::int AS stock
                       FROM warehouses w LEFT JOIN stock_movements sm ON sm.warehouse_id=w.id AND sm.product_id=%s
                       GROUP BY w.id, w.name ORDER BY w.name""", (product_id,))
        rows = cur.fetchall()
        cur.execute("SELECT id FROM products WHERE id=%s", (product_id,))
        exists = cur.fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"product_id": product_id, "warehouses": rows, "total_stock": sum(r["stock"] for r in rows)}


@app.post("/api/movements", status_code=201)
def create_movement(body: MovementRequest):
    with database() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM products WHERE id=%s", (body.product_id,))
        product = cur.fetchone()
        cur.execute("SELECT id FROM warehouses WHERE id=%s", (body.warehouse_id,))
        warehouse = cur.fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        if not warehouse:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        # Prevent a warehouse from going negative when stock is removed.
        if body.movement_type == "OUT":
            # Lock the product row so simultaneous stock-out requests for it are checked in sequence.
            cur.execute("SELECT id FROM products WHERE id=%s FOR UPDATE", (body.product_id,))
            cur.execute("""SELECT COALESCE(SUM(CASE WHEN movement_type='IN' THEN quantity ELSE -quantity END),0) AS stock
                           FROM stock_movements WHERE product_id=%s AND warehouse_id=%s""", (body.product_id, body.warehouse_id))
            available = cur.fetchone()["stock"]
            if available < body.quantity:
                raise HTTPException(status_code=409, detail="Not enough stock in this warehouse")
        cur.execute("""INSERT INTO stock_movements(product_id, warehouse_id, quantity, movement_type, note)
                       VALUES (%s,%s,%s,%s,%s) RETURNING id, product_id, warehouse_id, quantity, movement_type, note, created_at""",
                    (body.product_id, body.warehouse_id, body.quantity, body.movement_type, body.note))
        return cur.fetchone()


@app.get("/api/products/{product_id}/movements")
def product_movements(product_id: int):
    with database() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM products WHERE id=%s", (product_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Product not found")
        cur.execute("""SELECT sm.id, sm.product_id, sm.warehouse_id, w.name AS warehouse, sm.quantity,
                       sm.movement_type, sm.note, sm.created_at FROM stock_movements sm
                       JOIN warehouses w ON w.id=sm.warehouse_id WHERE sm.product_id=%s
                       ORDER BY sm.created_at DESC, sm.id DESC LIMIT 20""", (product_id,))
        return {"items": cur.fetchall()}


@app.get("/api/reports/reorder")
def reorder_report(_: str = Depends(current_user)):
    with database() as conn, conn.cursor() as cur:
        cur.execute("""SELECT p.id, p.sku, p.name, c.name AS category, p.reorder_level,
                       COALESCE(SUM(CASE WHEN sm.movement_type='IN' THEN sm.quantity ELSE -sm.quantity END),0)::int AS current_stock
                       FROM products p JOIN categories c ON c.id=p.category_id
                       LEFT JOIN stock_movements sm ON sm.product_id=p.id
                       GROUP BY p.id, c.name
                       HAVING COALESCE(SUM(CASE WHEN sm.movement_type='IN' THEN sm.quantity ELSE -sm.quantity END),0) < p.reorder_level
                       ORDER BY current_stock ASC, p.name""")
        return {"items": cur.fetchall()}
