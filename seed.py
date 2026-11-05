"""Seed RetailDesk with clearly-labelled SAMPLE data for demo purposes.

Creates:
  * Demo store "RetailDesk Demo Clothing Store"
  * Owner login:  demo@retaildesk.in  / demo1234
  * Staff login:  staff@retaildesk.in / staff1234
  * 12 sample clothing products, 5 sample customers
  * Sample bills spread over the last 7 days (so the dashboard has data)

Run:  python seed.py
Safe to re-run: it exits early if the demo owner already exists.
All data here is fictional sample data — no real users or sales.
"""
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app import models

Base.metadata.create_all(bind=engine)

PRODUCTS = [
    # name, sku, category, price, gst%, stock, low-stock threshold
    ("Men's Cotton T-Shirt", "TSHIRT-001", "Men", 499.0, 5.0, 120, 15),
    ("Men's Slim-Fit Jeans", "JEANS-001", "Men", 1299.0, 12.0, 60, 10),
    ("Men's Formal Shirt", "SHIRT-001", "Men", 899.0, 12.0, 45, 8),
    ("Women's Kurti", "KURTI-001", "Women", 799.0, 5.0, 80, 12),
    ("Women's Leggings", "LEG-001", "Women", 399.0, 5.0, 3, 10),      # low stock on purpose
    ("Women's Saree", "SAREE-001", "Women", 2499.0, 5.0, 25, 5),
    ("Kids T-Shirt (Pack of 2)", "KIDS-001", "Kids", 599.0, 5.0, 70, 10),
    ("Kids Frock", "KIDS-002", "Kids", 849.0, 5.0, 40, 8),
    ("Unisex Hoodie", "HOOD-001", "Unisex", 1099.0, 12.0, 2, 6),      # low stock on purpose
    ("Running Shoes", "SHOE-001", "Footwear", 1799.0, 18.0, 35, 6),
    ("Cotton Socks (Pack of 3)", "SOCK-001", "Accessories", 199.0, 12.0, 200, 25),
    ("Leather Wallet", "WALL-001", "Accessories", 649.0, 18.0, 28, 5),
]

CUSTOMERS = [
    ("Aarav Sharma", "9810011223", "aarav.sample@example.com"),
    ("Priya Nair", "9822033445", "priya.sample@example.com"),
    ("Rahul Verma", "9930055667", None),
    ("Sneha Kulkarni", "9845098765", "sneha.sample@example.com"),
    ("Vikram Reddy", "9703012345", None),
]


def main():
    db = SessionLocal()
    try:
        if db.query(models.User).filter(models.User.email == "demo@retaildesk.in").first():
            print("Seed data already exists (demo@retaildesk.in found). Nothing to do.")
            return

        store = models.Store(
            name="RetailDesk Demo Clothing Store",
            phone="080-45678901",
            gstin="29ABCDE1234F1Z5",  # sample GSTIN for demo invoices
            address="MG Road, Bengaluru, Karnataka 560001",
        )
        db.add(store)
        db.flush()

        owner = models.User(
            store_id=store.id, name="Demo Owner", email="demo@retaildesk.in",
            hashed_password=hash_password("demo1234"), role="owner",
        )
        staff = models.User(
            store_id=store.id, name="Demo Staff", email="staff@retaildesk.in",
            hashed_password=hash_password("staff1234"), role="staff",
        )
        db.add_all([owner, staff])
        db.flush()

        product_objs = []
        for name, sku, category, price, gst, stock, threshold in PRODUCTS:
            p = models.Product(
                store_id=store.id, name=name, sku=sku, category=category,
                price=price, gst_percent=gst, stock_qty=stock,
                low_stock_threshold=threshold,
            )
            db.add(p)
            product_objs.append(p)
        db.flush()

        customer_objs = []
        for name, phone, email in CUSTOMERS:
            c = models.Customer(store_id=store.id, name=name, phone=phone, email=email)
            db.add(c)
            customer_objs.append(c)
        db.flush()

        # ~14 sample bills across the last 7 days (never "today-only", so the
        # 7-day chart looks alive). Stock is deducted exactly like real billing.
        random.seed(42)
        bill_count = db.query(models.Bill).filter(models.Bill.store_id == store.id).count()
        for day_offset in range(6, -1, -1):
            bills_today = random.randint(1, 3)
            for _ in range(bills_today):
                chosen = random.sample(product_objs, random.randint(1, 3))
                subtotal, gst_total = 0.0, 0.0
                bill_count += 1
                created = datetime.now(timezone.utc) - timedelta(
                    days=day_offset, hours=random.randint(0, 8), minutes=random.randint(0, 59)
                )
                bill = models.Bill(
                    store_id=store.id,
                    bill_number=f"INV-{created.year}-{bill_count:04d}",
                    customer_id=random.choice(customer_objs).id if random.random() > 0.3 else None,
                    created_by=owner.id,
                    payment_mode=random.choice(["cash", "upi", "card"]),
                    created_at=created,
                )
                db.add(bill)
                db.flush()
                for product in chosen:
                    qty = random.randint(1, 3)
                    if product.stock_qty < qty:
                        continue
                    line_total = round(product.price * qty, 2)
                    gst_amt = round(line_total * product.gst_percent / 100.0, 2)
                    subtotal += line_total
                    gst_total += gst_amt
                    db.add(models.BillItem(
                        bill_id=bill.id, product_id=product.id,
                        product_name=product.name, quantity=qty,
                        unit_price=product.price, gst_percent=product.gst_percent,
                        line_total=line_total,
                    ))
                    product.stock_qty -= qty
                bill.subtotal = round(subtotal, 2)
                bill.gst_total = round(gst_total, 2)
                bill.grand_total = round(subtotal + gst_total, 2)

        db.commit()
        print("Seed complete (SAMPLE data only):")
        print(f"  Store:    {store.name}")
        print(f"  Owner:    demo@retaildesk.in / demo1234")
        print(f"  Staff:    staff@retaildesk.in / staff1234")
        print(f"  Products: {len(product_objs)}  Customers: {len(customer_objs)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
