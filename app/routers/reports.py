"""Dashboard & reporting routes. Owner-only: staff do not see full reports."""
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import require_owner
from ..database import get_db

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _day_start(dt: datetime) -> datetime:
    return datetime.combine(dt.date(), time.min, tzinfo=timezone.utc)


@router.get("/dashboard", response_model=schemas.DashboardStats)
def dashboard(
    db: Session = Depends(get_db),
    owner: models.User = Depends(require_owner),
):
    store_id = owner.store_id
    now = datetime.now(timezone.utc)
    today_start = _day_start(now)
    month_start = today_start.replace(day=1)

    bills_q = db.query(models.Bill).filter(models.Bill.store_id == store_id)

    revenue_today = (
        bills_q.filter(models.Bill.created_at >= today_start)
        .with_entities(func.coalesce(func.sum(models.Bill.grand_total), 0.0))
        .scalar()
    )
    revenue_month = (
        bills_q.filter(models.Bill.created_at >= month_start)
        .with_entities(func.coalesce(func.sum(models.Bill.grand_total), 0.0))
        .scalar()
    )
    bills_today = bills_q.filter(models.Bill.created_at >= today_start).count()
    bills_total = bills_q.count()
    products_total = (
        db.query(models.Product).filter(models.Product.store_id == store_id).count()
    )
    low_stock_count = (
        db.query(models.Product)
        .filter(
            models.Product.store_id == store_id,
            models.Product.stock_qty <= models.Product.low_stock_threshold,
        )
        .count()
    )

    # Top 5 products by quantity sold (all time for this store).
    top_rows = (
        db.query(
            models.BillItem.product_id,
            models.BillItem.product_name,
            func.sum(models.BillItem.quantity).label("qty"),
            func.sum(models.BillItem.line_total).label("revenue"),
        )
        .join(models.Bill, models.Bill.id == models.BillItem.bill_id)
        .filter(models.Bill.store_id == store_id)
        .group_by(models.BillItem.product_id, models.BillItem.product_name)
        .order_by(func.sum(models.BillItem.quantity).desc())
        .limit(5)
        .all()
    )
    top_products = [
        schemas.TopProduct(
            product_id=r.product_id,
            product_name=r.product_name,
            quantity_sold=int(r.qty or 0),
            revenue=float(r.revenue or 0.0),
        )
        for r in top_rows
    ]

    # Revenue by day for the last 7 days (including today), zero-filled.
    week_start = today_start - timedelta(days=6)
    week_bills = bills_q.filter(models.Bill.created_at >= week_start).all()
    per_day: dict[str, dict] = defaultdict(lambda: {"revenue": 0.0, "bills": 0})
    for bill in week_bills:
        created = bill.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        key = created.date().isoformat()
        per_day[key]["revenue"] += bill.grand_total
        per_day[key]["bills"] += 1

    last_7_days = []
    for offset in range(6, -1, -1):
        day = (today_start - timedelta(days=offset)).date().isoformat()
        entry = per_day.get(day, {"revenue": 0.0, "bills": 0})
        last_7_days.append(
            schemas.DayRevenue(date=day, revenue=round(entry["revenue"], 2), bills=entry["bills"])
        )

    return schemas.DashboardStats(
        revenue_today=round(float(revenue_today), 2),
        revenue_this_month=round(float(revenue_month), 2),
        bills_today=bills_today,
        bills_total=bills_total,
        products_total=products_total,
        low_stock_count=low_stock_count,
        top_products=top_products,
        last_7_days=last_7_days,
    )
