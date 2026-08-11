"""Authentication + authorization services (business logic, no HTTP concerns)."""

from fastapi import HTTPException, status

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import UserCreate
from sqlalchemy import select
from sqlalchemy.orm import Session


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def register(self, payload: UserCreate) -> User:
        """Create a new user. Raises 409 if the email is already registered."""
        existing = self.get_by_email(payload.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        user = User(
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self.db.scalar(stmt)

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def authenticate(self, email: str, password: str) -> User:
        """Verify credentials. Raises 401 on any failure (no user enumeration)."""
        user = self.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
