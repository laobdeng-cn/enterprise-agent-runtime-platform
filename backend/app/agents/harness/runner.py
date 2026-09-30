import json
from time import perf_counter
from uuid import UUID

from app.agents.harness.context import ContextBuilder
from app.agents.harness.contracts import (
    ContextPackage,
    HarnessResult,
    MemoryContextItem,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelToolDefinition,
    SkillContextItem,
    TokenUsage,
)
from app.agents.harness.errors import HarnessError
from app.agents.harness.hooks import (
    HarnessLifecycleContext,
    LifecycleHook,
    NoopLifecycleHook,
)
from app.agents.harness.providers.base import ModelProvider
from app.agents.harness.registry import ModelProviderRegistry
from app.models.agent import AgentVersion
from app.skills.contracts import SkillExecutionContext
from app.skills.executor import SkillExecutor


class AgentHarness:
    def __init__(
        self,
        *,
        providers: ModelProviderRegistry,
        skill_executor: SkillExecutor | None = None,
        context_builder: ContextBuilder | None = None,
        lifecycle_hook: LifecycleHook | None = None,
        max_tool_rounds: int = 4,
    ) -> None:
        self.providers = providers
        self.skill_executor = skill_executor
        self.context_builder = context_builder or ContextBuilder()
        self.lifecycle_hook = lifecycle_hook or NoopLifecycleHook()
        self.max_tool_rounds = max_tool_rounds

    async def run(
        self,
        *,
        agent_id: UUID,
        version: AgentVersion,
        user_input: str,
        additional_context: list[str] | None = None,
        granted_permissions: set[str] | None = None,
        skill_context: SkillExecutionContext | None = None,
        relevant_memory: list[MemoryContextItem] | None = None,
        prepared_context: ContextPackage | None = None,
    ) -> HarnessResult:
        context_package = prepared_context or self.prepare_context(
            version=version,
            user_input=user_input,
            additional_context=additional_context,
            relevant_memory=relevant_memory,
            granted_permissions=granted_permissions,
        )
        messages = context_package.to_messages()
        selected_names = set(context_package.selected_skill_names)
        selected_bound_versions = [
            skill_version
            for skill_version in version.bound_skill_versions
            if skill_version.skill.name in selected_names
        ]
        tools = self._tool_definitions(
            version,
            selected_names=selected_names,
        )
        lifecycle_context = HarnessLifecycleContext(
            agent_id=agent_id,
            agent_version_id=version.id,
            agent_version=version.version,
            provider=version.model_provider,
            model=version.model_name,
        )
        provider = self.providers.resolve(version.model_provider)
        started_at = perf_counter()
        total_usage = TokenUsage()
        tool_results: list[dict[str, object]] = []
        response_ids: list[str] = []
        runtime_context_rounds: list[dict[str, int]] = []

        for tool_round in range(self.max_tool_rounds + 1):
            request_messages, runtime_fit = self.context_builder.fit_runtime_messages(
                messages=messages,
                tools=tools,
                input_budget_tokens=(
                    context_package.trace.budget.input_budget_tokens
                ),
            )
            runtime_fit["round"] = tool_round
            runtime_context_rounds.append(runtime_fit)
            request = ModelRequest(
                model=version.model_name,
                messages=request_messages,
                temperature=version.temperature,
                max_tokens=version.max_tokens,
                tools=tools,
            )
            response = await self._invoke_model(
                provider=provider,
                lifecycle_context=lifecycle_context,
                request=request,
            )
            self._accumulate_usage(total_usage, response.usage)
            if response.response_id:
                response_ids.append(response.response_id)

            if not response.tool_calls:
                return HarnessResult(
                    agent_id=agent_id,
                    agent_version_id=version.id,
                    agent_version=version.version,
                    content=response.content,
                    provider=response.provider,
                    model=response.model,
                    finish_reason=response.finish_reason,
                    usage=total_usage,
                    duration_ms=(perf_counter() - started_at) * 1000,
                    tool_results=tool_results,
                    metadata={
                        "response_id": response.response_id,
                        "response_ids": response_ids,
                        "tool_rounds": tool_round,
                        "memory_ids": [
                            str(item.id)
                            for item in context_package.relevant_memory
                        ],
                        "memory_count": len(
                            context_package.relevant_memory
                        ),
                        "context_trace": context_package.trace.model_dump(
                            mode="json"
                        ),
                        "context_runtime_rounds": runtime_context_rounds,
                        "selected_skill_names": (
                            context_package.selected_skill_names
                        ),
                    },
                )

            if tool_round >= self.max_tool_rounds:
                raise HarnessError(
                    f"Agent exceeded maximum tool rounds ({self.max_tool_rounds})"
                )
            if self.skill_executor is None:
                raise HarnessError(
                    "Model proposed a tool call but no SkillExecutor is configured"
                )

            messages.append(
                ModelMessage(
                    role="assistant",
                    content=response.content or None,
                    tool_calls=response.tool_calls,
                )
            )

            for call in response.tool_calls:
                result = await self.skill_executor.execute(
                    call,
                    bound_versions=selected_bound_versions,
                    granted_permissions=set(granted_permissions or set()),
                    execution_context=skill_context,
                )
                result_payload = result.model_dump(mode="json")
                result_payload["arguments"] = dict(call.arguments)
                tool_results.append(result_payload)
                messages.append(
                    ModelMessage(
                        role="tool",
                        tool_call_id=call.id,
                        content=json.dumps(
                            result_payload,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    )
                )

        raise HarnessError("Agent Harness reached an unreachable tool-loop state")

    def prepare_context(
        self,
        *,
        version: AgentVersion,
        user_input: str,
        additional_context: list[str] | None = None,
        relevant_memory: list[MemoryContextItem] | None = None,
        granted_permissions: set[str] | None = None,
    ) -> ContextPackage:
        return self.context_builder.build(
            system_instructions=version.system_instructions,
            user_input=user_input,
            additional_context=additional_context,
            relevant_memory=relevant_memory,
            skill_candidates=self._skill_context_items(version),
            granted_permissions=set(granted_permissions or set()),
            context_policy=dict(version.context_policy),
            model_max_tokens=version.max_tokens,
        )

    async def _invoke_model(
        self,
        *,
        provider: ModelProvider,
        lifecycle_context: HarnessLifecycleContext,
        request: ModelRequest,
    ) -> ModelResponse:
        await self.lifecycle_hook.before_model_call(
            lifecycle_context,
            request,
        )
        try:
            response = await provider.invoke(request)
        except Exception as exc:
            await self.lifecycle_hook.on_model_error(
                lifecycle_context,
                request,
                exc,
            )
            raise

        await self.lifecycle_hook.after_model_call(
            lifecycle_context,
            request,
            response,
        )
        return response

    @staticmethod
    def _skill_context_items(
        version: AgentVersion,
    ) -> list[SkillContextItem]:
        return [
            SkillContextItem(
                name=skill_version.skill.name,
                description=skill_version.skill.description,
                input_schema=dict(skill_version.input_schema),
                required_permissions=list(
                    skill_version.required_permissions
                ),
                side_effect=skill_version.side_effect,
            )
            for skill_version in version.bound_skill_versions
            if skill_version.skill.status == "active"
        ]

    @staticmethod
    def _tool_definitions(
        version: AgentVersion,
        *,
        selected_names: set[str],
    ) -> list[ModelToolDefinition]:
        definitions = [
            ModelToolDefinition(
                name=skill_version.skill.name,
                description=skill_version.skill.description,
                parameters=dict(skill_version.input_schema),
            )
            for skill_version in version.bound_skill_versions
            if (
                skill_version.skill.status == "active"
                and skill_version.skill.name in selected_names
            )
        ]
        return sorted(definitions, key=lambda item: item.name)

    @staticmethod
    def _accumulate_usage(total: TokenUsage, usage: TokenUsage) -> None:
        total.prompt_tokens += usage.prompt_tokens
        total.completion_tokens += usage.completion_tokens
        total.total_tokens += usage.total_tokens
