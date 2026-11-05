"""Product & inventory routes."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_owner
from ..database import get_db

router = APIRouter(prefix="/api/products", tags=["products"])


def _to_out(product: models.Product) -> schemas.ProductOut:
    out = schemas.ProductOut.model_validate(product)
    out.is_low_stock = product.stock_qty <= product.low_stock_threshold
    return out


def _get_product_or_404(db: Session, product_id: int, store_id: int) -> models.Product:
    product = (
        db.query(models.Product)
        .filter(models.Product.id == product_id, models.Product.store_id == store_id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("", response_model=schemas.ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: schemas.ProductCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    duplicate = (
        db.query(models.Product)
        .filter(
            models.Product.store_id == current_user.store_id,
            models.Product.sku == payload.sku,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail=f"SKU '{payload.sku}' already exists in this store")
    product = models.Product(store_id=current_user.store_id, **payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return _to_out(product)


@router.get("", response_model=schemas.ProductPage)
def list_products(
    search: Optional[str] = Query(default=None, description="Match name, SKU or category"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Product).filter(models.Product.store_id == current_user.store_id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            (models.Product.name.ilike(like))
            | (models.Product.sku.ilike(like))
            | (models.Product.category.ilike(like))
        )
    total = query.count()
    items = (
        query.order_by(models.Product.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return schemas.ProductPage(
        total=total, page=page, page_size=page_size, items=[_to_out(p) for p in items]
    )


@router.get("/low-stock", response_model=list[schemas.ProductOut])
def low_stock_products(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Products at or below their low-stock threshold."""
    products = (
        db.query(models.Product)
        .filter(
            models.Product.store_id == current_user.store_id,
            models.Product.stock_qty <= models.Product.low_stock_threshold,
        )
        .order_by(models.Product.stock_qty)
        .all()
    )
    return [_to_out(p) for p in products]


@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _to_out(_get_product_or_404(db, product_id, current_user.store_id))


@router.put("/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: int,
    payload: schemas.ProductUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    product = _get_product_or_404(db, product_id, current_user.store_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return _to_out(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    owner: models.User = Depends(require_owner),  # staff cannot delete products
):
    product = _get_product_or_404(db, product_id, owner.store_id)
    db.delete(product)
    db.commit()
    return None
