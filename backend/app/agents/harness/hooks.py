from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.agents.harness.contracts import ModelRequest, ModelResponse


@dataclass(frozen=True)
class HarnessLifecycleContext:
    agent_id: UUID
    agent_version_id: UUID
    agent_version: int
    provider: str
    model: str


class LifecycleHook(Protocol):
    async def before_model_call(
        self,
        context: HarnessLifecycleContext,
        request: ModelRequest,
    ) -> None: ...

    async def after_model_call(
        self,
        context: HarnessLifecycleContext,
        request: ModelRequest,
        response: ModelResponse,
    ) -> None: ...

    async def on_model_error(
        self,
        context: HarnessLifecycleContext,
        request: ModelRequest,
        error: Exception,
    ) -> None: ...


class NoopLifecycleHook:
    async def before_model_call(
        self,
        context: HarnessLifecycleContext,
        request: ModelRequest,
    ) -> None:
        return None

    async def after_model_call(
        self,
        context: HarnessLifecycleContext,
        request: ModelRequest,
        response: ModelResponse,
    ) -> None:
        return None

    async def on_model_error(
        self,
        context: HarnessLifecycleContext,
        request: ModelRequest,
        error: Exception,
    ) -> None:
        return None
