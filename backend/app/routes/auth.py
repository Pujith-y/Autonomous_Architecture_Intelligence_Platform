from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from app.database.postgres import get_db
from app.models.user_model import User
from app.schemas.user_schemas import UserCreate, LoginRequest
from app.services.auth.dependencies import get_current_user
from app.services.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.get("/db-test")
def database_test(
    db: Session = Depends(get_db),
):
    user = db.query(User).all()
    return {
        "user_count" : len(user)
    }

@router.post("/register")
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    user = User(
        email=user_data.email,
        password_hash=hash_password(
            user_data.password
        ),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
    }

@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.email == form_data.username
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    if not verify_password(
        form_data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    access_token = create_access_token(
        subject=str(user.id)
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }

@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "is_active": current_user.is_active,
    }