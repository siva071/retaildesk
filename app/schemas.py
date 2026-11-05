"""Pydantic request/response schemas (API contracts)."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

# Emails are validated as plain strings here to avoid an extra dependency
# (pydantic's EmailStr requires the email-validator package).


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class RegisterOwner(BaseModel):
    store_name: str = Field(..., min_length=2, max_length=120)
    name: str = Field(..., min_length=2, max_length=120)
    email: str
    password: str = Field(..., min_length=6, max_length=72)
    phone: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None


class CreateStaff(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: str
    password: str = Field(..., min_length=6, max_length=72)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    store_id: int

    class Config:
        from_attributes = True


# --------------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------------- #
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    sku: str = Field(..., min_length=1, max_length=60)
    category: Optional[str] = None
    price: float = Field(..., gt=0)
    gst_percent: float = Field(default=5.0, ge=0, le=28)
    stock_qty: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=5, ge=0)


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    gst_percent: Optional[float] = Field(default=None, ge=0, le=28)
    stock_qty: Optional[int] = Field(default=None, ge=0)
    low_stock_threshold: Optional[int] = Field(default=None, ge=0)


class ProductOut(BaseModel):
    id: int
    name: str
    sku: str
    category: Optional[str]
    price: float
    gst_percent: float
    stock_qty: int
    low_stock_threshold: int
    is_low_stock: bool = False

    class Config:
        from_attributes = True


class ProductPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ProductOut]


# --------------------------------------------------------------------------- #
# Customers
# --------------------------------------------------------------------------- #
class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    phone: Optional[str] = None
    email: Optional[str] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class CustomerOut(BaseModel):
    id: int
    name: str
    phone: Optional[str]
    email: Optional[str]

    class Config:
        from_attributes = True


# --------------------------------------------------------------------------- #
# Bills
# --------------------------------------------------------------------------- #
class BillItemIn(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)


class BillCreate(BaseModel):
    customer_id: Optional[int] = None
    payment_mode: str = "cash"
    items: List[BillItemIn] = Field(..., min_length=1)


class BillItemOut(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    gst_percent: float
    line_total: float

    class Config:
        from_attributes = True


class BillOut(BaseModel):
    id: int
    bill_number: str
    customer_id: Optional[int]
    subtotal: float
    gst_total: float
    grand_total: float
    payment_mode: str
    created_at: datetime
    items: List[BillItemOut] = []

    class Config:
        from_attributes = True


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
class TopProduct(BaseModel):
    product_id: int
    product_name: str
    quantity_sold: int
    revenue: float


class DayRevenue(BaseModel):
    date: str
    revenue: float
    bills: int


class DashboardStats(BaseModel):
    revenue_today: float
    revenue_this_month: float
    bills_today: int
    bills_total: int
    products_total: int
    low_stock_count: int
    top_products: List[TopProduct]
    last_7_days: List[DayRevenue]
