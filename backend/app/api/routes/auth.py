from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.identity import User
from app.schemas.auth import AccessTokenResponse, CurrentUserResponse, LoginRequest
from app.services.auth import authenticate_user, permission_codes

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    request: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AccessTokenResponse:
    user = await authenticate_user(session, request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(str(user.id), user.username)
    return AccessTokenResponse(
        access_token=token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        roles=sorted(role.name for role in current_user.roles),
        permissions=sorted(permission_codes(current_user)),
    )
