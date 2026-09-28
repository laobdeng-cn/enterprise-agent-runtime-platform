from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import InvalidAccessTokenError, decode_access_token
from app.db.session import get_db
from app.models.identity import User
from app.services.auth import get_user_by_id, permission_codes

bearer_scheme = HTTPBearer(auto_error=False)
PermissionDependency = Callable[..., Awaitable[User]]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(str(payload["sub"]))
    except (InvalidAccessTokenError, ValueError, KeyError):
        raise unauthorized from None

    user = await get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise unauthorized

    return user


def require_permissions(*required_permissions: str) -> PermissionDependency:
    async def dependency(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        granted = permission_codes(current_user)
        missing = sorted(set(required_permissions) - granted)

        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Missing required permissions",
                    "missing_permissions": missing,
                },
            )

        return current_user

    return dependency
