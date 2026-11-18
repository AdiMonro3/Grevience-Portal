from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.deps import DB, CurrentUser
from app.models import Role, User
from app.schemas.auth import LocationIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["auth"])


def _token_response(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: DB):
    """Citizen sign-up. Officers and admins are created by the seed script / admin."""
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(
        name=body.name.strip(),
        email=email,
        phone=body.phone,
        password_hash=hash_password(body.password),
        role=Role.CITIZEN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenOut)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB):
    """Form fields `username` (= email) and `password`, so Swagger's Authorize button works."""
    user = db.scalar(select(User).where(User.email == form.username.strip().lower()))
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled")
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@users_router.put("/me/location", response_model=UserOut)
def update_location(body: LocationIn, user: CurrentUser, db: DB):
    user.lat, user.lng, user.address = body.lat, body.lng, body.address
    db.commit()
    return user
