"""Billing routes.

The most important rule in the whole app lives here: a bill and its stock
deductions commit together or not at all. All line items are validated
first; if any product has insufficient stock the request fails and the
database transaction is rolled back, so no stock ever changes for a
half-completed bill.
"""
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/bills", tags=["bills"])


def _next_bill_number(db: Session, store_id: int) -> str:
    count = db.query(models.Bill).filter(models.Bill.store_id == store_id).count()
    year = datetime.now(timezone.utc).year
    return f"INV-{year}-{count + 1:04d}"


@router.post("", response_model=schemas.BillOut, status_code=status.HTTP_201_CREATED)
def create_bill(
    payload: schemas.BillCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Optional customer must belong to this store.
    if payload.customer_id is not None:
        customer = (
            db.query(models.Customer)
            .filter(
                models.Customer.id == payload.customer_id,
                models.Customer.store_id == current_user.store_id,
            )
            .first()
        )
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

    # Merge duplicate product lines so stock is checked against the total.
    quantities: dict[int, int] = {}
    for item in payload.items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity

    try:
        # 1) Validate everything BEFORE mutating anything.
        products: dict[int, models.Product] = {}
        for product_id, qty in quantities.items():
            product = (
                db.query(models.Product)
                .filter(
                    models.Product.id == product_id,
                    models.Product.store_id == current_user.store_id,
                )
                .first()
            )
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
            if product.stock_qty < qty:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Insufficient stock for '{product.name}': "
                        f"requested {qty}, available {product.stock_qty}"
                    ),
                )
            products[product_id] = product

        # 2) Build the bill with price/GST snapshots and deduct stock.
        subtotal = 0.0
        gst_total = 0.0
        bill = models.Bill(
            store_id=current_user.store_id,
            bill_number=_next_bill_number(db, current_user.store_id),
            customer_id=payload.customer_id,
            created_by=current_user.id,
            payment_mode=payload.payment_mode,
        )
        db.add(bill)
        db.flush()  # assign bill.id

        for product_id, qty in quantities.items():
            product = products[product_id]
            line_total = round(product.price * qty, 2)
            gst_amount = round(line_total * product.gst_percent / 100.0, 2)
            subtotal += line_total
            gst_total += gst_amount
            db.add(
                models.BillItem(
                    bill_id=bill.id,
                    product_id=product.id,
                    product_name=product.name,
                    quantity=qty,
                    unit_price=product.price,
                    gst_percent=product.gst_percent,
                    line_total=line_total,
                )
            )
            product.stock_qty -= qty  # deducted inside the same transaction

        bill.subtotal = round(subtotal, 2)
        bill.gst_total = round(gst_total, 2)
        bill.grand_total = round(subtotal + gst_total, 2)

        # 3) One commit: bill + items + stock changes succeed or fail together.
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    db.refresh(bill)
    return bill


@router.get("", response_model=list[schemas.BillOut])
def list_bills(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Bill)
        .filter(models.Bill.store_id == current_user.store_id)
        .order_by(models.Bill.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )


def _get_bill_or_404(db: Session, bill_id: int, store_id: int) -> models.Bill:
    bill = (
        db.query(models.Bill)
        .filter(models.Bill.id == bill_id, models.Bill.store_id == store_id)
        .first()
    )
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill


@router.get("/{bill_id}", response_model=schemas.BillOut)
def get_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_bill_or_404(db, bill_id, current_user.store_id)


@router.get("/{bill_id}/invoice")
def download_invoice(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Generate a GST invoice PDF for a completed bill (reportlab)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    bill = _get_bill_or_404(db, bill_id, current_user.store_id)
    store = db.query(models.Store).filter(models.Store.id == bill.store_id).first()
    customer_name = bill.customer.name if bill.customer else "Walk-in Customer"

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 20 * mm

    def line(text, dy=6 * mm, bold=False, size=11):
        nonlocal y
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        pdf.drawString(20 * mm, y, text)
        y -= dy

    line("TAX INVOICE", bold=True, size=16)
    line(store.name if store else "RetailDesk Store", bold=True, size=13)
    if store and store.address:
        line(store.address, size=9)
    if store and store.gstin:
        line(f"GSTIN: {store.gstin}", size=9)
    y -= 2 * mm
    line(f"Invoice No: {bill.bill_number}")
    line(f"Date: {bill.created_at.strftime('%d-%m-%Y %H:%M') if bill.created_at else '-'}")
    line(f"Billed To: {customer_name}")
    line(f"Payment Mode: {bill.payment_mode.upper()}")
    y -= 2 * mm

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(20 * mm, y, "Item")
    pdf.drawString(95 * mm, y, "Qty")
    pdf.drawString(110 * mm, y, "Rate")
    pdf.drawString(135 * mm, y, "GST%")
    pdf.drawString(155 * mm, y, "Amount")
    y -= 2 * mm
    pdf.line(20 * mm, y, width - 20 * mm, y)
    y -= 5 * mm
    pdf.setFont("Helvetica", 10)
    for item in bill.items:
        pdf.drawString(20 * mm, y, item.product_name[:38])
        pdf.drawString(95 * mm, y, str(item.quantity))
        pdf.drawString(110 * mm, y, f"{item.unit_price:.2f}")
        pdf.drawString(135 * mm, y, f"{item.gst_percent:.0f}")
        pdf.drawString(155 * mm, y, f"{item.line_total:.2f}")
        y -= 5.5 * mm

    pdf.line(20 * mm, y, width - 20 * mm, y)
    y -= 6 * mm
    line(f"Subtotal: Rs. {bill.subtotal:.2f}")
    line(f"GST Total: Rs. {bill.gst_total:.2f}")
    line(f"Grand Total: Rs. {bill.grand_total:.2f}", bold=True, size=12)
    y -= 4 * mm
    line("Thank you for shopping with us!", size=9)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{bill.bill_number}.pdf"'},
    )
