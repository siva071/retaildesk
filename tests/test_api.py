"""End-to-end API tests for RetailDesk (run against a temp SQLite DB)."""
import itertools

from conftest import auth

_sku_counter = itertools.count(1)


def make_product(client, token, stock=10, threshold=5, price=100.0):
    n = next(_sku_counter)
    res = client.post(
        "/api/products",
        json={
            "name": f"Test Product {n}",
            "sku": f"TEST-{n:03d}",
            "category": "Test",
            "price": price,
            "gst_percent": 5.0,
            "stock_qty": stock,
            "low_stock_threshold": threshold,
        },
        headers=auth(token),
    )
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------- auth ----- #
def test_login_wrong_password_rejected(client, owner_token):
    res = client.post(
        "/api/auth/login", data={"username": "owner@test.in", "password": "WRONG-password"}
    )
    assert res.status_code == 401


def test_login_success_and_me(client, owner_token):
    res = client.post(
        "/api/auth/login", data={"username": "owner@test.in", "password": "owner1234"}
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    me = client.get("/api/auth/me", headers=auth(token))
    assert me.status_code == 200
    assert me.json()["role"] == "owner"
    assert me.json()["email"] == "owner@test.in"


def test_protected_route_needs_token(client):
    assert client.get("/api/products").status_code == 401


# ------------------------------------------------------------ products ----- #
def test_product_create(client, owner_token):
    product = make_product(client, owner_token, stock=25)
    assert product["stock_qty"] == 25
    assert product["is_low_stock"] is False
    fetched = client.get(f"/api/products/{product['id']}", headers=auth(owner_token))
    assert fetched.status_code == 200
    assert fetched.json()["sku"] == product["sku"]


def test_staff_cannot_delete_product(client, owner_token, staff_token):
    product = make_product(client, owner_token)
    res = client.delete(f"/api/products/{product['id']}", headers=auth(staff_token))
    assert res.status_code == 403
    # Owner can:
    res = client.delete(f"/api/products/{product['id']}", headers=auth(owner_token))
    assert res.status_code == 204


def test_low_stock_endpoint(client, owner_token):
    low = make_product(client, owner_token, stock=2, threshold=5)
    res = client.get("/api/products/low-stock", headers=auth(owner_token))
    assert res.status_code == 200
    ids = [p["id"] for p in res.json()]
    assert low["id"] in ids
    assert all(p["is_low_stock"] for p in res.json())


# --------------------------------------------------------------- bills ----- #
def test_bill_creation_reduces_stock_and_totals(client, owner_token):
    product = make_product(client, owner_token, stock=10, price=200.0)
    res = client.post(
        "/api/bills",
        json={"items": [{"product_id": product["id"], "quantity": 3}], "payment_mode": "upi"},
        headers=auth(owner_token),
    )
    assert res.status_code == 201, res.text
    bill = res.json()
    # 3 x 200 = 600 subtotal, 5% GST = 30, grand total 630.
    assert bill["subtotal"] == 600.0
    assert bill["gst_total"] == 30.0
    assert bill["grand_total"] == 630.0
    after = client.get(f"/api/products/{product['id']}", headers=auth(owner_token)).json()
    assert after["stock_qty"] == 7


def test_bill_with_insufficient_stock_rolls_back_fully(client, owner_token):
    plenty = make_product(client, owner_token, stock=5)
    scarce = make_product(client, owner_token, stock=2)
    bills_before = client.get("/api/bills", headers=auth(owner_token)).json()

    res = client.post(
        "/api/bills",
        json={
            "items": [
                {"product_id": plenty["id"], "quantity": 3},   # fine on its own
                {"product_id": scarce["id"], "quantity": 99},  # impossible
            ]
        },
        headers=auth(owner_token),
    )
    assert res.status_code == 400

    # NOTHING changed: not even the first (valid) product lost stock,
    # and no bill was recorded. That is the atomicity guarantee.
    p1 = client.get(f"/api/products/{plenty['id']}", headers=auth(owner_token)).json()
    p2 = client.get(f"/api/products/{scarce['id']}", headers=auth(owner_token)).json()
    assert p1["stock_qty"] == 5
    assert p2["stock_qty"] == 2
    bills_after = client.get("/api/bills", headers=auth(owner_token)).json()
    assert len(bills_after) == len(bills_before)


# ------------------------------------------------------------- reports ----- #
def test_staff_cannot_view_reports(client, staff_token):
    res = client.get("/api/reports/dashboard", headers=auth(staff_token))
    assert res.status_code == 403


def test_dashboard_returns_numbers(client, owner_token):
    res = client.get("/api/reports/dashboard", headers=auth(owner_token))
    assert res.status_code == 200
    data = res.json()
    assert data["bills_total"] >= 1
    assert data["revenue_this_month"] > 0
    assert len(data["last_7_days"]) == 7
    assert data["low_stock_count"] >= 1


def test_invoice_pdf_download(client, owner_token):
    product = make_product(client, owner_token, stock=4)
    bill = client.post(
        "/api/bills",
        json={"items": [{"product_id": product["id"], "quantity": 1}]},
        headers=auth(owner_token),
    ).json()
    res = client.get(f"/api/bills/{bill['id']}/invoice", headers=auth(owner_token))
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:4] == b"%PDF"
