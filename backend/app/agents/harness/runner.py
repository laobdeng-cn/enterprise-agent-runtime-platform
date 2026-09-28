from time import perf_counter
from uuid import UUID

from app.agents.harness.context import ContextBuilder
from app.agents.harness.contracts import HarnessResult, ModelRequest
from app.agents.harness.hooks import (
    HarnessLifecycleContext,
    LifecycleHook,
    NoopLifecycleHook,
)
from app.agents.harness.registry import ModelProviderRegistry
from app.models.agent import AgentVersion


class AgentHarness:
    def __init__(
        self,
        *,
        providers: ModelProviderRegistry,
        context_builder: ContextBuilder | None = None,
        lifecycle_hook: LifecycleHook | None = None,
    ) -> None:
        self.providers = providers
        self.context_builder = context_builder or ContextBuilder()
        self.lifecycle_hook = lifecycle_hook or NoopLifecycleHook()

    async def run(
        self,
        *,
        agent_id: UUID,
        version: AgentVersion,
        user_input: str,
        additional_context: list[str] | None = None,
    ) -> HarnessResult:
        context_package = self.context_builder.build(
            system_instructions=version.system_instructions,
            user_input=user_input,
            additional_context=additional_context,
        )
        request = ModelRequest(
            model=version.model_name,
            messages=context_package.to_messages(),
            temperature=version.temperature,
            max_tokens=version.max_tokens,
        )
        lifecycle_context = HarnessLifecycleContext(
            agent_id=agent_id,
            agent_version_id=version.id,
            agent_version=version.version,
            provider=version.model_provider,
            model=version.model_name,
        )
        provider = self.providers.resolve(version.model_provider)

        await self.lifecycle_hook.before_model_call(lifecycle_context, request)
        started_at = perf_counter()

        try:
            response = await provider.invoke(request)
        except Exception as exc:
            await self.lifecycle_hook.on_model_error(
                lifecycle_context,
                request,
                exc,
            )
            raise

        duration_ms = (perf_counter() - started_at) * 1000
        await self.lifecycle_hook.after_model_call(
            lifecycle_context,
            request,
            response,
        )

        return HarnessResult(
            agent_id=agent_id,
            agent_version_id=version.id,
            agent_version=version.version,
            content=response.content,
            provider=response.provider,
            model=response.model,
            finish_reason=response.finish_reason,
            usage=response.usage,
            duration_ms=duration_ms,
            metadata={"response_id": response.response_id},
        )
