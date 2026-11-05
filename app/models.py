"""SQLAlchemy ORM models for RetailDesk.

Every business record belongs to a Store, so multiple shops can use the
system without ever seeing each other's data (multi-tenancy by store_id).
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(20), nullable=True)
    gstin = Column(String(20), nullable=True)  # shop's GST number, printed on invoices
    address = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    users = relationship("User", back_populates="store")
    products = relationship("Product", back_populates="store")
    customers = relationship("Customer", back_populates="store")
    bills = relationship("Bill", back_populates="store")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(160), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="staff")  # "owner" | "staff"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    store = relationship("Store", back_populates="users")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("store_id", "sku", name="uq_product_store_sku"),)

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    sku = Column(String(60), nullable=False, index=True)
    category = Column(String(80), nullable=True)
    price = Column(Float, nullable=False)  # selling price per unit (incl. nothing; GST added on bill)
    gst_percent = Column(Float, nullable=False, default=5.0)
    stock_qty = Column(Integer, nullable=False, default=0)
    low_stock_threshold = Column(Integer, nullable=False, default=5)
    created_at = Column(DateTime, default=utcnow)

    store = relationship("Store", back_populates="products")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(20), nullable=True, index=True)
    email = Column(String(160), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    store = relationship("Store", back_populates="customers")
    bills = relationship("Bill", back_populates="customer")


class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    bill_number = Column(String(30), nullable=False, index=True)  # e.g. INV-2026-0001
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    subtotal = Column(Float, nullable=False, default=0.0)  # before GST
    gst_total = Column(Float, nullable=False, default=0.0)
    grand_total = Column(Float, nullable=False, default=0.0)  # subtotal + gst_total
    payment_mode = Column(String(20), nullable=False, default="cash")  # cash | upi | card
    created_at = Column(DateTime, default=utcnow, index=True)

    store = relationship("Store", back_populates="bills")
    customer = relationship("Customer", back_populates="bills")
    items = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan")


class BillItem(Base):
    """One line of a bill. Price and GST are snapshotted at billing time so
    later product edits never change old bills."""

    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product_name = Column(String(160), nullable=False)  # snapshot
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)  # snapshot
    gst_percent = Column(Float, nullable=False)  # snapshot
    line_total = Column(Float, nullable=False)  # qty * unit_price (before GST)

    bill = relationship("Bill", back_populates="items")
    product = relationship("Product")
