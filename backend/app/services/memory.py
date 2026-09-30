import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.session import async_session_maker
from app.memory.contracts import (
    MemoryScope,
    MemorySource,
    MemoryStatus,
    MemoryType,
)
from app.memory.ranking import memory_relevance_score
from app.models.agent import Agent
from app.models.identity import User
from app.models.memory import Memory
from app.models.runtime import AgentRun
from app.schemas.memory import MemoryCreateRequest, MemoryUpdateRequest
from app.services.auth import permission_codes


class MemoryNotFoundError(LookupError):
    pass


class MemoryAccessDeniedError(PermissionError):
    pass


class MemoryScopeError(ValueError):
    pass


class MemoryStatusError(ValueError):
    pass


@dataclass(slots=True)
class RankedMemory:
    memory: Memory
    score: float


def _now() -> datetime:
    return datetime.now(UTC)


def _is_admin(principal: User) -> bool:
    return "admin:manage" in permission_codes(principal)


def _normalize_content(content: str) -> str:
    return " ".join(content.strip().split())


def _fingerprint(content: str) -> str:
    normalized = _normalize_content(content).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _nullable_equals(column: Any, value: UUID | None) -> Any:
    return column.is_(None) if value is None else column == value


async def _resolve_scope_targets(
    session: AsyncSession,
    *,
    owner_user_id: UUID,
    scope: MemoryScope,
    agent_id: UUID | None,
    run_id: UUID | None,
) -> tuple[UUID | None, UUID | None]:
    if scope == MemoryScope.USER:
        if agent_id is not None or run_id is not None:
            raise MemoryScopeError(
                "USER scope cannot include agent_id or run_id"
            )
        return None, None

    if scope == MemoryScope.AGENT:
        if agent_id is None or run_id is not None:
            raise MemoryScopeError(
                "AGENT scope requires agent_id and forbids run_id"
            )
        result = await session.execute(
            select(Agent.id).where(Agent.id == agent_id)
        )
        if result.scalar_one_or_none() is None:
            raise MemoryScopeError(f"Agent {agent_id} was not found")
        return agent_id, None

    if scope == MemoryScope.RUN:
        if run_id is None:
            raise MemoryScopeError("RUN scope requires run_id")
        run = await session.get(AgentRun, run_id)
        if run is None:
            raise MemoryScopeError(f"Run {run_id} was not found")
        if run.created_by_user_id != owner_user_id:
            raise MemoryAccessDeniedError(
                "A Run-scoped Memory must belong to the Run creator"
            )
        if agent_id is not None and agent_id != run.agent_id:
            raise MemoryScopeError(
                "agent_id does not match the Run's Agent"
            )
        return run.agent_id, run.id

    raise MemoryScopeError(f"Unsupported Memory scope '{scope}'")


class MemoryWriter:
    async def write(
        self,
        session: AsyncSession,
        *,
        owner_user_id: UUID,
        memory_type: MemoryType,
        scope: MemoryScope,
        content: str,
        label: str | None = None,
        agent_id: UUID | None = None,
        run_id: UUID | None = None,
        importance: float = 0.5,
        ttl_seconds: int | None = None,
        metadata: dict[str, Any] | None = None,
        source: MemorySource = MemorySource.USER,
        source_ref: str | None = None,
    ) -> Memory:
        target_agent_id, target_run_id = await _resolve_scope_targets(
            session,
            owner_user_id=owner_user_id,
            scope=scope,
            agent_id=agent_id,
            run_id=run_id,
        )

        normalized_content = _normalize_content(content)
        if not normalized_content:
            raise ValueError("Memory content cannot be empty")

        fingerprint = _fingerprint(normalized_content)
        effective_ttl = ttl_seconds
        if (
            effective_ttl is None
            and settings.memory_default_ttl_days > 0
        ):
            effective_ttl = settings.memory_default_ttl_days * 86400

        expires_at = (
            _now() + timedelta(seconds=effective_ttl)
            if effective_ttl is not None
            else None
        )

        duplicate_result = await session.execute(
            select(Memory).where(
                Memory.owner_user_id == owner_user_id,
                Memory.memory_type == memory_type.value,
                Memory.scope == scope.value,
                Memory.status == MemoryStatus.ACTIVE.value,
                Memory.fingerprint == fingerprint,
                _nullable_equals(Memory.agent_id, target_agent_id),
                _nullable_equals(Memory.run_id, target_run_id),
            )
        )
        existing = duplicate_result.scalar_one_or_none()
        if existing is not None:
            existing.importance = max(existing.importance, importance)
            if label is not None:
                existing.label = label
            if metadata:
                existing.metadata_json = {
                    **existing.metadata_json,
                    **metadata,
                }
            if expires_at is not None:
                if existing.expires_at is None or expires_at > existing.expires_at:
                    existing.expires_at = expires_at
            existing.updated_at = _now()
            await session.flush()
            return existing

        memory = Memory(
            owner_user_id=owner_user_id,
            agent_id=target_agent_id,
            run_id=target_run_id,
            memory_type=memory_type.value,
            scope=scope.value,
            status=MemoryStatus.ACTIVE.value,
            label=label,
            content=normalized_content,
            metadata_json=dict(metadata or {}),
            source=source.value,
            source_ref=source_ref,
            importance=importance,
            fingerprint=fingerprint,
            expires_at=expires_at,
        )
        session.add(memory)
        await session.flush()
        return memory


class MemoryRetriever:
    def __init__(
        self,
        *,
        candidate_limit: int,
        min_score: float,
    ) -> None:
        self.candidate_limit = candidate_limit
        self.min_score = min_score

    async def retrieve(
        self,
        session: AsyncSession,
        *,
        owner_user_id: UUID,
        query: str,
        agent_id: UUID | None = None,
        run_id: UUID | None = None,
        memory_types: set[MemoryType] | None = None,
        limit: int = 8,
        track_access: bool = True,
    ) -> list[RankedMemory]:
        now = _now()
        scope_filters = [
            (
                Memory.scope == MemoryScope.USER.value
            )
        ]
        if agent_id is not None:
            scope_filters.append(
                (Memory.scope == MemoryScope.AGENT.value)
                & (Memory.agent_id == agent_id)
            )
        if run_id is not None:
            scope_filters.append(
                (Memory.scope == MemoryScope.RUN.value)
                & (Memory.run_id == run_id)
            )

        statement = (
            select(Memory)
            .where(
                Memory.owner_user_id == owner_user_id,
                Memory.status == MemoryStatus.ACTIVE.value,
                or_(Memory.expires_at.is_(None), Memory.expires_at > now),
                or_(*scope_filters),
            )
            .order_by(
                Memory.importance.desc(),
                Memory.updated_at.desc(),
            )
            .limit(self.candidate_limit)
        )
        if memory_types:
            statement = statement.where(
                Memory.memory_type.in_(
                    sorted(item.value for item in memory_types)
                )
            )

        result = await session.execute(statement)
        candidates = list(result.scalars().all())

        ranked: list[RankedMemory] = []
        for memory in candidates:
            score = memory_relevance_score(
                query=query,
                content=memory.content,
                importance=memory.importance,
                scope=MemoryScope(memory.scope),
                updated_at=memory.updated_at,
                now=now,
            )
            if score >= self.min_score:
                ranked.append(RankedMemory(memory=memory, score=score))

        ranked.sort(
            key=lambda item: (
                item.score,
                item.memory.importance,
                item.memory.updated_at,
            ),
            reverse=True,
        )
        selected = ranked[:limit]

        if track_access:
            for item in selected:
                item.memory.access_count += 1
                item.memory.last_accessed_at = now
            if selected:
                await session.flush()

        return selected

    async def retrieve_for_run(
        self,
        session: AsyncSession,
        *,
        run: AgentRun,
        principal_id: UUID,
        query: str,
        limit: int,
    ) -> list[RankedMemory]:
        if run.created_by_user_id != principal_id:
            raise MemoryAccessDeniedError(
                "Run Memory retrieval requires the Run creator"
            )
        return await self.retrieve(
            session,
            owner_user_id=principal_id,
            query=query,
            agent_id=run.agent_id,
            run_id=run.id,
            limit=limit,
        )


async def get_memory(
    session: AsyncSession,
    memory_id: UUID,
    *,
    principal: User,
    include_deleted: bool = False,
) -> Memory:
    result = await session.execute(
        select(Memory).where(Memory.id == memory_id)
    )
    memory = result.scalar_one_or_none()
    if memory is None or (
        memory.status == MemoryStatus.DELETED.value
        and not include_deleted
    ):
        raise MemoryNotFoundError(f"Memory {memory_id} was not found")

    if memory.owner_user_id != principal.id and not _is_admin(principal):
        raise MemoryAccessDeniedError(
            f"Memory {memory_id} is not accessible to this principal"
        )
    return memory


async def list_memories(
    session: AsyncSession,
    principal: User,
    *,
    status: MemoryStatus = MemoryStatus.ACTIVE,
    memory_type: MemoryType | None = None,
    scope: MemoryScope | None = None,
    limit: int = 100,
) -> list[Memory]:
    statement = (
        select(Memory)
        .where(
            Memory.owner_user_id == principal.id,
            Memory.status == status.value,
        )
        .order_by(Memory.updated_at.desc())
        .limit(limit)
    )
    if memory_type is not None:
        statement = statement.where(
            Memory.memory_type == memory_type.value
        )
    if scope is not None:
        statement = statement.where(Memory.scope == scope.value)

    result = await session.execute(statement)
    return list(result.scalars().all())


async def create_memory(
    session: AsyncSession,
    principal: User,
    payload: MemoryCreateRequest,
) -> Memory:
    memory = await memory_writer.write(
        session,
        owner_user_id=principal.id,
        memory_type=payload.memory_type,
        scope=payload.scope,
        content=payload.content,
        label=payload.label,
        agent_id=payload.agent_id,
        run_id=payload.run_id,
        importance=payload.importance,
        ttl_seconds=payload.ttl_seconds,
        metadata=payload.metadata,
        source=MemorySource.USER,
        source_ref=str(principal.id),
    )
    await session.commit()
    return memory


async def update_memory(
    session: AsyncSession,
    principal: User,
    memory_id: UUID,
    payload: MemoryUpdateRequest,
) -> Memory:
    memory = await get_memory(
        session,
        memory_id,
        principal=principal,
    )

    if payload.status == MemoryStatus.DELETED:
        raise MemoryStatusError(
            "Use DELETE /api/memories/{id} to delete Memory"
        )
    if payload.content is not None:
        content = _normalize_content(payload.content)
        if not content:
            raise ValueError("Memory content cannot be empty")
        memory.content = content
        memory.fingerprint = _fingerprint(content)
    if payload.label is not None:
        memory.label = payload.label
    if payload.importance is not None:
        memory.importance = payload.importance
    if payload.status is not None:
        memory.status = payload.status.value
    if payload.metadata is not None:
        memory.metadata_json = dict(payload.metadata)

    memory.updated_at = _now()
    await session.commit()
    return memory


async def delete_memory(
    session: AsyncSession,
    principal: User,
    memory_id: UUID,
) -> Memory:
    memory = await get_memory(
        session,
        memory_id,
        principal=principal,
    )
    memory.status = MemoryStatus.DELETED.value
    memory.updated_at = _now()
    await session.commit()
    return memory


async def search_memories(
    session: AsyncSession,
    principal: User,
    *,
    query: str,
    agent_id: UUID | None = None,
    run_id: UUID | None = None,
    memory_types: set[MemoryType] | None = None,
    limit: int = 20,
) -> list[RankedMemory]:
    effective_agent_id = agent_id
    if run_id is not None:
        run = await session.get(AgentRun, run_id)
        if run is None:
            raise MemoryScopeError(f"Run {run_id} was not found")
        if run.created_by_user_id != principal.id:
            raise MemoryAccessDeniedError(
                "Memory search cannot inspect another user's Run"
            )
        if agent_id is not None and agent_id != run.agent_id:
            raise MemoryScopeError(
                "agent_id does not match the requested Run"
            )
        effective_agent_id = run.agent_id
    elif agent_id is not None:
        result = await session.execute(
            select(Agent.id).where(Agent.id == agent_id)
        )
        if result.scalar_one_or_none() is None:
            raise MemoryScopeError(f"Agent {agent_id} was not found")

    ranked = await memory_retriever.retrieve(
        session,
        owner_user_id=principal.id,
        query=query,
        agent_id=effective_agent_id,
        run_id=run_id,
        memory_types=memory_types,
        limit=limit,
        track_access=True,
    )
    await session.commit()
    return ranked


class MemoryCapabilityService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory

    async def search(
        self,
        *,
        run_id: UUID,
        principal_id: UUID,
        query: str,
        memory_types: set[MemoryType] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            run = await session.get(AgentRun, run_id)
            if run is None:
                raise MemoryNotFoundError(f"Run {run_id} was not found")
            if run.created_by_user_id != principal_id:
                raise MemoryAccessDeniedError(
                    "Memory Skill cannot access another user's Run"
                )

            ranked = await memory_retriever.retrieve(
                session,
                owner_user_id=principal_id,
                query=query,
                agent_id=run.agent_id,
                run_id=run.id,
                memory_types=memory_types,
                limit=limit,
                track_access=True,
            )
            await session.commit()
            return [
                {
                    "id": str(item.memory.id),
                    "memory_type": item.memory.memory_type,
                    "scope": item.memory.scope,
                    "content": item.memory.content,
                    "score": item.score,
                    "importance": item.memory.importance,
                    "source": item.memory.source,
                }
                for item in ranked
            ]

    async def write(
        self,
        *,
        run_id: UUID,
        principal_id: UUID,
        memory_type: MemoryType,
        scope: MemoryScope,
        content: str,
        label: str | None,
        importance: float,
        ttl_seconds: int | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        async with self.session_factory() as session:
            run = await session.get(AgentRun, run_id)
            if run is None:
                raise MemoryNotFoundError(f"Run {run_id} was not found")
            if run.created_by_user_id != principal_id:
                raise MemoryAccessDeniedError(
                    "Memory Skill cannot write another user's Memory"
                )

            agent_id = run.agent_id if scope == MemoryScope.AGENT else None
            target_run_id = run.id if scope == MemoryScope.RUN else None
            memory = await memory_writer.write(
                session,
                owner_user_id=principal_id,
                memory_type=memory_type,
                scope=scope,
                content=content,
                label=label,
                agent_id=agent_id,
                run_id=target_run_id,
                importance=importance,
                ttl_seconds=ttl_seconds,
                metadata=metadata,
                source=MemorySource.AGENT,
                source_ref=str(run.id),
            )
            await session.commit()
            return {
                "id": str(memory.id),
                "memory_type": memory.memory_type,
                "scope": memory.scope,
                "status": memory.status,
                "content": memory.content,
                "importance": memory.importance,
                "expires_at": (
                    memory.expires_at.isoformat()
                    if memory.expires_at is not None
                    else None
                ),
            }


memory_writer = MemoryWriter()
memory_retriever = MemoryRetriever(
    candidate_limit=settings.memory_search_candidate_limit,
    min_score=settings.memory_search_min_score,
)


memory_capabilities = MemoryCapabilityService(
    session_factory=async_session_maker,
)
