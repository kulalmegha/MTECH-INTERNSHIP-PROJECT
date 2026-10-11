"""
/auth router — login and current-user endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import CurrentUser, DBSession
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserRead
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Obtain a JWT access token",
)
async def login(body: LoginRequest, db: DBSession) -> TokenResponse:
    """
    Authenticate with username + password.  Returns a JWT Bearer token valid
    for ``ACCESS_TOKEN_EXPIRE_MINUTES`` (default 60 minutes).
    """
    result = await db.execute(select(User).where(User.username == body.username))
    user: User | None = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(subject=user.username, role=user.role.value)
    return TokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Return the currently authenticated user",
)
async def get_me(current_user: CurrentUser) -> UserRead:
    """
    Returns the profile of the user whose Bearer token is presented.
    Works for both counsellors and victims.
    """
    return UserRead.model_validate(current_user)
