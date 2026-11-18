"""Shared FastAPI dependencies: DB session, current user, role checks."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Complaint, Role, User
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

DB = Annotated[Session, Depends(get_db)]


def get_current_user(db: DB, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not logged in or session expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise unauthorized
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role):
    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Only {', '.join(roles)} can do this")
        return user

    return checker


Citizen = Annotated[User, Depends(require_roles(Role.CITIZEN))]
Officer = Annotated[User, Depends(require_roles(Role.OFFICER))]
Admin = Annotated[User, Depends(require_roles(Role.ADMIN))]


def get_complaint_or_404(db: Session, ticket_no: str) -> Complaint:
    c = db.scalar(select(Complaint).where(Complaint.ticket_no == ticket_no.upper()))
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return c
