"""RetailDesk — Smart Billing & Inventory for Retail Stores.

FastAPI application entry point. Serves the JSON API under /api/* and the
single-page web UI from app/static/.

Deployment notes:
  * PORT is read by the server command (uvicorn $PORT), not here.
  * When the UI is hosted separately (e.g. Vercel) and calls this API
    cross-origin, set ALLOWED_ORIGINS to that origin (comma-separated),
    or leave the default "*" for the public demo.
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .routers import auth, bills, customers, products, reports

# Create tables on startup (fine for this project scale; a larger system
# would use Alembic migrations).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RetailDesk API",
    description="Smart billing & inventory system for retail stores.",
    version="1.0.0",
)

# CORS — needed when the frontend is hosted on a different origin (Vercel)
# than the backend (Render). Default "*" suits the free demo; lock it down
# by setting ALLOWED_ORIGINS=https://your-app.vercel.app in production.
_allowed = os.getenv("ALLOWED_ORIGINS", "*").strip()
allow_origins = ["*"] if _allowed == "*" else [o.strip() for o in _allowed.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(customers.router)
app.include_router(bills.router)
app.include_router(reports.router)

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "RetailDesk"}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    # The UI uses RELATIVE asset paths (styles.css, app.js, config.js), so it
    # works identically when served from /static/ here and when the static
    # folder is deployed on its own to Vercel.
    return RedirectResponse(url="/static/index.html")
