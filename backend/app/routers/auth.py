import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.config import settings
from app.deps import DB, CurrentUser
from app.models import Role, User
from app.schemas.auth import AuthProvidersOut, GoogleLoginIn, LocationIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password
from app.services.google_auth import verify_google_credential

router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["auth"])


def _token_response(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: DB):
    """Citizen sign-up. Returns the new account; the user then logs in with `/auth/login`.
    Officers and admins are created by the seed script / admin."""
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
    return user


@router.post("/login", response_model=TokenOut)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB):
    """Form fields `username` (= email) and `password`, so Swagger's Authorize button works."""
    user = db.scalar(select(User).where(User.email == form.username.strip().lower()))
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled")
    return _token_response(user)


@router.get("/providers", response_model=AuthProvidersOut)
def providers():
    """Public sign-in options for the frontend (a Google client ID is not a secret)."""
    return AuthProvidersOut(google_client_id=settings.google_client_id or None)


@router.post("/google", response_model=TokenOut)
def google_login(body: GoogleLoginIn, db: DB):
    """Sign in with Google: post the `credential` (ID token) from Google's button.

    - Known Google account -> logs in.
    - Existing account with the same (Google-verified) email -> links it, then logs in.
    - Otherwise -> creates a citizen account and logs in.
    """
    claims = verify_google_credential(body.credential)
    sub, email = claims["sub"], claims["email"].lower()

    user = db.scalar(select(User).where(User.google_sub == sub))
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            name = (claims.get("name") or email.split("@")[0]).strip()[:120]
            user = User(
                name=name,
                email=email,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                role=Role.CITIZEN,
            )
            db.add(user)
        elif user.google_sub is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "This email is linked to a different Google account")
        user.google_sub = sub

    db.flush()  # fills column defaults (is_active) on a brand-new account
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled")
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@users_router.put("/me/location", response_model=UserOut)
def update_location(body: LocationIn, user: CurrentUser, db: DB):
    user.lat, user.lng, user.address = body.lat, body.lng, body.address
    db.commit()
    return user
