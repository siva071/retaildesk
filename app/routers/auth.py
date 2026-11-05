"""Auth routes: register a store owner, log in, manage staff."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import create_access_token, get_current_user, hash_password, require_owner, verify_password
from ..database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
def register_owner(payload: schemas.RegisterOwner, db: Session = Depends(get_db)):
    """Create a new store and its owner account in one step."""
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    store = models.Store(
        name=payload.store_name,
        phone=payload.phone,
        gstin=payload.gstin,
        address=payload.address,
    )
    db.add(store)
    db.flush()  # get store.id

    owner = models.User(
        store_id=store.id,
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role="owner",
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return {"access_token": create_access_token(owner), "token_type": "bearer"}


@router.post("/login", response_model=schemas.Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 password login — `username` field carries the email."""
    user = db.query(models.User).filter(models.User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": create_access_token(user), "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/staff", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def create_staff(
    payload: schemas.CreateStaff,
    db: Session = Depends(get_db),
    owner: models.User = Depends(require_owner),
):
    """Owners can add staff accounts to their own store."""
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    staff = models.User(
        store_id=owner.store_id,
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role="staff",
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff
