# RetailDesk — Smart Billing & Inventory for Retail Stores

A complete, working billing + inventory web application built for small
retail shops (the demo data is a clothing store). A shop owner registers,
adds products, bills customers at the counter, watches stock reduce
automatically, downloads GST invoices as PDFs, and tracks revenue on a
dashboard — with staff accounts that have limited permissions.

**Live Demo:** https://retaildesk-api.onrender.com — demo login `demo@retaildesk.in` / `demo1234`

> Sample/seed data in this repo is fictional demo data. No real users or sales.

## Features

- **Auth & roles** — register a store (owner account), login with JWT,
  owners can create staff accounts. Staff can bill and manage products but
  **cannot delete products and cannot view reports** (enforced in the API).
- **Products & inventory** — CRUD with SKU, category, price, GST %,
  stock quantity, per-product low-stock threshold, search + pagination,
  and a low-stock listing.
- **Billing** — multi-item bills. Stock is deducted **atomically**: if any
  item lacks stock, the whole bill is rejected and *no* stock changes.
  Each bill line snapshots the price and GST % at billing time, so editing
  a product later never changes old bills.
- **GST invoice PDF** — every bill can be downloaded as a formatted tax
  invoice (store name, GSTIN, item table, GST breakup, grand total).
- **Customers** — CRUD, optionally linked to bills.
- **Dashboard / reports** — revenue today & this month, bill counts,
  top-5 products by quantity, low-stock count, and revenue for the last
  7 days (rendered as a chart in the UI).
- **Single-page web UI** — login, dashboard with stat cards + chart,
  products, billing counter, customers. No build step (vanilla JS).

## Tech Stack

| Layer     | Technology |
|-----------|------------|
| Backend   | Python, FastAPI, Pydantic v2 |
| ORM / DB  | SQLAlchemy 2.x — PostgreSQL (hosted) or SQLite (local demo) via `DATABASE_URL` |
| Auth      | JWT (python-jose), bcrypt password hashing (passlib) |
| Invoice   | reportlab (PDF generation) |
| Frontend  | HTML / CSS / vanilla JavaScript (served as static files) |
| Tests     | pytest + FastAPI TestClient (11 tests) |
| Packaging | Docker + docker-compose, Render Blueprint, Procfile |

## Architecture

```
 Browser (static UI: index.html + app.js)
    │  fetch() with JWT in Authorization header
    ▼
 FastAPI app (app/main.py)
    ├── /api/auth       register / login / staff        ── app/routers/auth.py
    ├── /api/products   CRUD, search, low-stock         ── app/routers/products.py
    ├── /api/customers  CRUD                            ── app/routers/customers.py
    ├── /api/bills      create (atomic), list, invoice  ── app/routers/bills.py
    └── /api/reports    dashboard stats (owner only)    ── app/routers/reports.py
    │
    ▼  SQLAlchemy ORM (app/models.py, app/database.py)
 PostgreSQL (Neon / docker)  —  or SQLite file locally
```

Everything is scoped by `store_id`, so many shops can share one deployment
without seeing each other's data.

### Database schema (summary)

- **stores** — id, name, phone, gstin, address
- **users** — id, store_id → stores, name, email (unique), hashed_password, role (`owner`/`staff`)
- **products** — id, store_id, name, sku (unique per store), category, price, gst_percent, stock_qty, low_stock_threshold
- **customers** — id, store_id, name, phone, email
- **bills** — id, store_id, bill_number, customer_id (nullable), created_by, subtotal, gst_total, grand_total, payment_mode, created_at
- **bill_items** — id, bill_id → bills, product_id, product_name / unit_price / gst_percent *(snapshots)*, quantity, line_total

## Quickstart — local (SQLite, no Docker)

```bash
pip install -r requirements.txt
python seed.py                                   # demo data + logins
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 and log in:

| Role  | Email               | Password   |
|-------|---------------------|------------|
| Owner | demo@retaildesk.in | demo1234   |
| Staff | staff@retaildesk.in | staff1234  |

## Run with Docker (PostgreSQL)

```bash
docker compose up --build
```

Starts Postgres + the app (seeded automatically) on http://localhost:8000.

## Deploy free (Vercel + Render + Neon)

See **[DEPLOY.md](DEPLOY.md)** — step-by-step: free Neon Postgres →
Render free web service for the API → Vercel for the frontend, including
how the frontend finds the backend (`window.API_BASE` in
`app/static/config.js`).

## Tests

```bash
python -m pytest        # 11 tests: auth, RBAC, billing atomicity, low-stock, invoice…
```

The most important test: a bill whose second item has insufficient stock
must fail **and** leave the first item's stock untouched (full rollback).

## API endpoints

| Method | Path | Who | Description |
|--------|------|-----|-------------|
| POST | `/api/auth/register` | public | Create store + owner, returns JWT |
| POST | `/api/auth/login` | public | Login (form: username=email, password) |
| GET | `/api/auth/me` | any | Current user |
| POST | `/api/auth/staff` | owner | Create staff account |
| POST | `/api/products` | any | Create product |
| GET | `/api/products?search=&page=&page_size=` | any | List / search products |
| GET | `/api/products/low-stock` | any | Products at/below threshold |
| GET/PUT | `/api/products/{id}` | any | Get / update product |
| DELETE | `/api/products/{id}` | **owner** | Delete product |
| POST/GET | `/api/customers` | any | Create / list customers |
| GET/PUT/DELETE | `/api/customers/{id}` | any / **owner** (delete) | Customer detail |
| POST | `/api/bills` | any | Create bill (atomic stock deduction) |
| GET | `/api/bills` | any | Recent bills |
| GET | `/api/bills/{id}` | any | Bill detail |
| GET | `/api/bills/{id}/invoice` | any | GST invoice PDF download |
| GET | `/api/reports/dashboard` | **owner** | Revenue stats, top products, 7-day series |
| GET | `/api/health` | public | Health check |

Interactive API docs (Swagger UI) are built in at `/docs`.

## Project structure

```
retaildesk/
├── app/
│   ├── main.py          # app setup, CORS, routers, static UI
│   ├── database.py      # engine/session; SQLite ⇄ Postgres via DATABASE_URL
│   ├── models.py        # SQLAlchemy models
│   ├── schemas.py       # Pydantic request/response contracts
│   ├── auth.py          # bcrypt hashing, JWT, role dependencies
│   ├── routers/         # auth, products, customers, bills, reports
│   └── static/          # index.html, styles.css, app.js, config.js (API base)
├── tests/               # pytest suite (temp SQLite DB)
├── seed.py              # fictional demo data + demo logins
├── requirements.txt
├── Dockerfile, docker-compose.yml
├── Procfile, render.yaml
└── DEPLOY.md
```

## Resume bullets (for the project owner)

- Built **RetailDesk**, a full-stack billing & inventory system for retail
  stores using **Python, FastAPI, SQLAlchemy and PostgreSQL**, with a
  vanilla-JS single-page frontend.
- Implemented **JWT authentication with role-based access control**
  (owner/staff) and bcrypt password hashing.
- Engineered **atomic billing transactions** — multi-item bills deduct
  stock in a single DB transaction with full rollback on insufficient
  stock; line items snapshot price/GST so historical bills never change.
- Designed a **normalized, multi-tenant schema** (stores, users, products,
  customers, bills, bill_items) with per-store SKU uniqueness and
  low-stock alerting.
- Added **GST invoice PDF generation** (reportlab) and a **reports API**
  (revenue trends, top products) feeding a dashboard chart.
- Wrote **11 pytest tests** covering auth, RBAC and transaction rollback;
  containerised with **Docker** and structured for free-tier deployment
  (Neon + Render + Vercel).
