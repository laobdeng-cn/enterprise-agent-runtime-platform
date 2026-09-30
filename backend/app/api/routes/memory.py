from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_permissions
from app.db.session import get_db
from app.memory.contracts import MemoryScope, MemoryStatus, MemoryType
from app.models.identity import User
from app.models.memory import Memory
from app.schemas.memory import (
    MemoryCreateRequest,
    MemoryResponse,
    MemorySearchResult,
    MemoryUpdateRequest,
)
from app.services.memory import (
    MemoryAccessDeniedError,
    MemoryNotFoundError,
    MemoryScopeError,
    MemoryStatusError,
    create_memory,
    delete_memory,
    get_memory,
    list_memories,
    search_memories,
    update_memory,
)

router = APIRouter(prefix="/api/memories", tags=["memory"])

MemoryReader = Annotated[
    User,
    Depends(require_permissions("memory:read")),
]
MemoryWriter = Annotated[
    User,
    Depends(require_permissions("memory:write")),
]
MemoryDeleter = Annotated[
    User,
    Depends(require_permissions("memory:delete")),
]


def to_memory_response(memory: Memory) -> MemoryResponse:
    return MemoryResponse(
        id=memory.id,
        owner_user_id=memory.owner_user_id,
        agent_id=memory.agent_id,
        run_id=memory.run_id,
        memory_type=MemoryType(memory.memory_type),
        scope=MemoryScope(memory.scope),
        status=MemoryStatus(memory.status),
        label=memory.label,
        content=memory.content,
        metadata=dict(memory.metadata_json),
        source=memory.source,
        source_ref=memory.source_ref,
        importance=memory.importance,
        expires_at=memory.expires_at,
        access_count=memory.access_count,
        last_accessed_at=memory.last_accessed_at,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


def _memory_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MemoryNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(exc, MemoryAccessDeniedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    if isinstance(exc, (MemoryScopeError, MemoryStatusError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Memory operation failed",
    )


@router.get("", response_model=list[MemoryResponse])
async def memories_index(
    principal: MemoryReader,
    session: Annotated[AsyncSession, Depends(get_db)],
    memory_type: Annotated[MemoryType | None, Query()] = None,
    scope: Annotated[MemoryScope | None, Query()] = None,
    memory_status: Annotated[
        MemoryStatus,
        Query(alias="status"),
    ] = MemoryStatus.ACTIVE,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[MemoryResponse]:
    memories = await list_memories(
        session,
        principal,
        status=memory_status,
        memory_type=memory_type,
        scope=scope,
        limit=limit,
    )
    return [to_memory_response(item) for item in memories]


@router.post(
    "",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def memories_create(
    payload: MemoryCreateRequest,
    principal: MemoryWriter,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MemoryResponse:
    try:
        memory = await create_memory(session, principal, payload)
    except Exception as exc:
        await session.rollback()
        raise _memory_http_error(exc) from exc
    return to_memory_response(memory)


@router.get(
    "/search",
    response_model=list[MemorySearchResult],
)
async def memories_search(
    principal: MemoryReader,
    session: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str, Query(max_length=20_000)] = "",
    agent_id: Annotated[UUID | None, Query()] = None,
    run_id: Annotated[UUID | None, Query()] = None,
    types: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[MemorySearchResult]:
    memory_types: set[MemoryType] | None = None
    if types:
        try:
            memory_types = {
                MemoryType(item.strip().upper())
                for item in types.split(",")
                if item.strip()
            }
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid Memory type in 'types'",
            ) from exc

    try:
        ranked = await search_memories(
            session,
            principal,
            query=q,
            agent_id=agent_id,
            run_id=run_id,
            memory_types=memory_types,
            limit=limit,
        )
    except Exception as exc:
        await session.rollback()
        raise _memory_http_error(exc) from exc

    return [
        MemorySearchResult(
            **to_memory_response(item.memory).model_dump(),
            score=item.score,
        )
        for item in ranked
    ]


@router.get("/{memory_id}", response_model=MemoryResponse)
async def memories_show(
    memory_id: UUID,
    principal: MemoryReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MemoryResponse:
    try:
        memory = await get_memory(
            session,
            memory_id,
            principal=principal,
        )
    except Exception as exc:
        raise _memory_http_error(exc) from exc
    return to_memory_response(memory)


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def memories_update(
    memory_id: UUID,
    payload: MemoryUpdateRequest,
    principal: MemoryWriter,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MemoryResponse:
    try:
        memory = await update_memory(
            session,
            principal,
            memory_id,
            payload,
        )
    except Exception as exc:
        await session.rollback()
        raise _memory_http_error(exc) from exc
    return to_memory_response(memory)


@router.delete("/{memory_id}", response_model=MemoryResponse)
async def memories_delete(
    memory_id: UUID,
    principal: MemoryDeleter,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MemoryResponse:
    try:
        memory = await delete_memory(
            session,
            principal,
            memory_id,
        )
    except Exception as exc:
        await session.rollback()
        raise _memory_http_error(exc) from exc
    return to_memory_response(memory)
