"""Customer routes."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_owner
from ..database import get_db

router = APIRouter(prefix="/api/customers", tags=["customers"])


def _get_customer_or_404(db: Session, customer_id: int, store_id: int) -> models.Customer:
    customer = (
        db.query(models.Customer)
        .filter(models.Customer.id == customer_id, models.Customer.store_id == store_id)
        .first()
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post("", response_model=schemas.CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: schemas.CustomerCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    customer = models.Customer(store_id=current_user.store_id, **payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("", response_model=list[schemas.CustomerOut])
def list_customers(
    search: Optional[str] = Query(default=None, description="Match name or phone"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Customer).filter(models.Customer.store_id == current_user.store_id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            (models.Customer.name.ilike(like)) | (models.Customer.phone.ilike(like))
        )
    return query.order_by(models.Customer.name).all()


@router.get("/{customer_id}", response_model=schemas.CustomerOut)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_customer_or_404(db, customer_id, current_user.store_id)


@router.put("/{customer_id}", response_model=schemas.CustomerOut)
def update_customer(
    customer_id: int,
    payload: schemas.CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    customer = _get_customer_or_404(db, customer_id, current_user.store_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    owner: models.User = Depends(require_owner),
):
    customer = _get_customer_or_404(db, customer_id, owner.store_id)
    db.delete(customer)
    db.commit()
    return None
