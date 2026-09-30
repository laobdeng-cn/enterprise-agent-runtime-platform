from typing import Any

from app.agents.harness.contracts import (
    ContextBudget,
    ContextDecision,
    ContextPackage,
    ContextTrace,
    MemoryContextItem,
    ModelMessage,
    ModelToolDefinition,
    SkillContextItem,
)
from app.context.budget import (
    ContextBudgetExceededError,
    ContextPolicy,
    TokenBudgetManager,
    resolve_context_policy,
    token_budget_manager,
)
from app.context.compression import ContextCompressor, context_compressor
from app.context.skill_selector import SkillSelector, skill_selector
from app.context.tokenizer import TokenEstimator, token_estimator
from app.core.config import settings


def _preview(value: str, limit: int = 180) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 2].rstrip() + " …"


class ContextBuilder:
    """Token-budgeted Context Engineering pipeline.

    System instructions and the current user request are mandatory. Additional
    context, durable Memory, Skill definitions, and tool history are bounded
    independently and emit inclusion/exclusion metadata for inspection.
    """

    def __init__(
        self,
        *,
        estimator: TokenEstimator | None = None,
        compressor: ContextCompressor | None = None,
        selector: SkillSelector | None = None,
        budget_manager: TokenBudgetManager | None = None,
    ) -> None:
        self.estimator = estimator or token_estimator
        self.compressor = compressor or context_compressor
        self.selector = selector or skill_selector
        self.budget_manager = budget_manager or token_budget_manager

    def build(
        self,
        *,
        system_instructions: str,
        user_input: str,
        additional_context: list[str] | None = None,
        relevant_memory: list[MemoryContextItem] | None = None,
        skill_candidates: list[SkillContextItem] | None = None,
        granted_permissions: set[str] | None = None,
        context_policy: dict[str, Any] | None = None,
        model_max_tokens: int | None = None,
    ) -> ContextPackage:
        policy = self._resolve_policy(
            context_policy or {},
            model_max_tokens=model_max_tokens,
        )
        decisions: list[ContextDecision] = []

        system_tokens = self.estimator.estimate_message(
            ModelMessage(role="system", content=system_instructions)
        )
        user_tokens = self.estimator.estimate_message(
            ModelMessage(role="user", content=user_input)
        )
        mandatory_tokens = system_tokens + user_tokens

        if mandatory_tokens > policy.initial_budget_tokens:
            raise ContextBudgetExceededError(
                "System instructions plus the current user request exceed "
                "the initial Context budget; refusing to silently truncate "
                "authoritative input"
            )

        decisions.extend(
            [
                ContextDecision(
                    component_id="system",
                    kind="system",
                    label="System instructions",
                    status="included",
                    reason="mandatory_authority",
                    priority=100,
                    original_tokens=system_tokens,
                    used_tokens=system_tokens,
                    preview=_preview(system_instructions),
                ),
                ContextDecision(
                    component_id="user",
                    kind="user",
                    label="Current user request",
                    status="included",
                    reason="mandatory_current_request",
                    priority=100,
                    original_tokens=user_tokens,
                    used_tokens=user_tokens,
                    preview=_preview(user_input),
                ),
            ]
        )

        allocation = self.budget_manager.allocate(
            policy,
            mandatory_tokens=mandatory_tokens,
        )

        fitted_additional, additional_decisions = self._fit_additional(
            items=list(additional_context or []),
            query=user_input,
            budget=allocation.additional_context_tokens,
            item_max_tokens=policy.item_max_tokens,
        )
        decisions.extend(additional_decisions)
        used_additional_tokens = sum(
            item.used_tokens
            for item in additional_decisions
            if item.status != "excluded"
        )

        effective_memory_budget = self.budget_manager.reflow_memory(
            policy,
            allocation,
            used_additional_tokens=used_additional_tokens,
        )
        fitted_memory, memory_decisions = self._fit_memory(
            memories=list(relevant_memory or []),
            query=user_input,
            budget=effective_memory_budget,
            item_max_tokens=policy.item_max_tokens,
        )
        decisions.extend(memory_decisions)
        used_memory_tokens = sum(
            item.used_tokens
            for item in memory_decisions
            if item.status != "excluded"
        )

        effective_skill_budget = self.budget_manager.reflow_skills(
            policy,
            allocation,
            used_additional_tokens=used_additional_tokens,
            used_memory_tokens=used_memory_tokens,
        )
        selected_skill_names, skill_decisions = self._fit_skills(
            candidates=list(skill_candidates or []),
            query=user_input,
            granted_permissions=set(granted_permissions or set()),
            budget=effective_skill_budget,
            skill_limit=policy.skill_limit,
            fallback_skill_count=policy.fallback_skill_count,
        )
        decisions.extend(skill_decisions)

        package = ContextPackage(
            system_instructions=system_instructions,
            user_input=user_input,
            additional_context=fitted_additional,
            relevant_memory=fitted_memory,
            selected_skill_names=selected_skill_names,
            trace=ContextTrace(
                budget=ContextBudget(
                    context_window_tokens=policy.context_window_tokens,
                    reserved_output_tokens=policy.reserved_output_tokens,
                    runtime_reserve_tokens=policy.runtime_reserve_tokens,
                    input_budget_tokens=policy.input_budget_tokens,
                    initial_budget_tokens=policy.initial_budget_tokens,
                    used_tokens=0,
                    remaining_tokens=policy.initial_budget_tokens,
                    message_tokens=0,
                    tool_tokens=0,
                ),
                decisions=decisions,
                selected_skill_names=selected_skill_names,
                excluded_skill_names=sorted(
                    {
                        item.label
                        for item in decisions
                        if item.kind == "skill" and item.status == "excluded"
                    }
                ),
                compression_count=sum(
                    1
                    for item in decisions
                    if item.status == "compressed"
                ),
                policy=self._policy_dict(policy),
            ),
        )

        messages = package.to_messages()
        selected_tools = self._selected_tool_definitions(
            skill_candidates=list(skill_candidates or []),
            selected_names=set(selected_skill_names),
        )
        message_tokens = self.estimator.estimate_messages(messages)
        tool_tokens = self.estimator.estimate_tools(selected_tools)
        used_tokens = message_tokens + tool_tokens

        if used_tokens > policy.initial_budget_tokens:
            raise ContextBudgetExceededError(
                "Context planning exceeded the initial token budget after "
                "message/tool serialization"
            )

        package.trace.budget = ContextBudget(
            context_window_tokens=policy.context_window_tokens,
            reserved_output_tokens=policy.reserved_output_tokens,
            runtime_reserve_tokens=policy.runtime_reserve_tokens,
            input_budget_tokens=policy.input_budget_tokens,
            initial_budget_tokens=policy.initial_budget_tokens,
            used_tokens=used_tokens,
            remaining_tokens=policy.initial_budget_tokens - used_tokens,
            message_tokens=message_tokens,
            tool_tokens=tool_tokens,
        )
        return package

    def fit_runtime_messages(
        self,
        *,
        messages: list[ModelMessage],
        tools: list[ModelToolDefinition],
        input_budget_tokens: int,
    ) -> tuple[list[ModelMessage], dict[str, int]]:
        fitted = [message.model_copy(deep=True) for message in messages]
        original_tokens = (
            self.estimator.estimate_messages(fitted)
            + self.estimator.estimate_tools(tools)
        )
        if original_tokens <= input_budget_tokens:
            return fitted, {
                "original_tokens": original_tokens,
                "used_tokens": original_tokens,
                "compressed_tool_messages": 0,
            }

        compressed_count = 0
        for message in fitted:
            if message.role != "tool" or not message.content:
                continue

            current_tokens = (
                self.estimator.estimate_messages(fitted)
                + self.estimator.estimate_tools(tools)
            )
            overflow = current_tokens - input_budget_tokens
            if overflow <= 0:
                break

            original_tool_tokens = self.estimator.estimate_text(
                message.content
            )
            target = max(
                48,
                original_tool_tokens - overflow - 24,
            )
            result = self.compressor.compress(
                message.content,
                token_budget=target,
            )
            message.content = (
                "[Context Engineering compressed tool result]\n"
                + result.text
            )
            compressed_count += 1

        used_tokens = (
            self.estimator.estimate_messages(fitted)
            + self.estimator.estimate_tools(tools)
        )
        if used_tokens > input_budget_tokens:
            raise ContextBudgetExceededError(
                "Tool history exceeded the runtime Context budget even after "
                "compressing tool-result messages"
            )

        return fitted, {
            "original_tokens": original_tokens,
            "used_tokens": used_tokens,
            "compressed_tool_messages": compressed_count,
        }

    def _fit_additional(
        self,
        *,
        items: list[str],
        query: str,
        budget: int,
        item_max_tokens: int,
    ) -> tuple[list[str], list[ContextDecision]]:
        included: list[str] = []
        decisions: list[ContextDecision] = []
        remaining = budget

        for index, item in enumerate(items, start=1):
            original_tokens = self.estimator.estimate_text(item)
            target = min(item_max_tokens, remaining)
            if target <= 0:
                decisions.append(
                    ContextDecision(
                        component_id=f"additional:{index}",
                        kind="additional_context",
                        label=f"Additional context {index}",
                        status="excluded",
                        reason="additional_context_budget_exhausted",
                        priority=90,
                        original_tokens=original_tokens,
                        used_tokens=0,
                        preview=_preview(item),
                    )
                )
                continue

            result = self.compressor.compress(
                item,
                token_budget=target,
                query=query,
            )
            if not result.text:
                status = "excluded"
                reason = "additional_context_budget_exhausted"
                used_tokens = 0
            else:
                included.append(result.text)
                remaining -= result.used_tokens
                status = "compressed" if result.compressed else "included"
                reason = (
                    "compressed_to_component_budget"
                    if result.compressed
                    else "within_component_budget"
                )
                used_tokens = result.used_tokens

            decisions.append(
                ContextDecision(
                    component_id=f"additional:{index}",
                    kind="additional_context",
                    label=f"Additional context {index}",
                    status=status,
                    reason=reason,
                    priority=90,
                    original_tokens=original_tokens,
                    used_tokens=used_tokens,
                    preview=_preview(result.text or item),
                )
            )

        return included, decisions

    def _fit_memory(
        self,
        *,
        memories: list[MemoryContextItem],
        query: str,
        budget: int,
        item_max_tokens: int,
    ) -> tuple[list[MemoryContextItem], list[ContextDecision]]:
        included: list[MemoryContextItem] = []
        decisions: list[ContextDecision] = []
        remaining = budget

        ordered = sorted(
            memories,
            key=lambda item: (item.score, item.importance),
            reverse=True,
        )
        for memory in ordered:
            original_tokens = self.estimator.estimate_text(memory.content)
            target = min(item_max_tokens, remaining)
            if target <= 0:
                decisions.append(
                    ContextDecision(
                        component_id=f"memory:{memory.id}",
                        kind="memory",
                        label=str(memory.id),
                        status="excluded",
                        reason="memory_budget_exhausted",
                        priority=80,
                        original_tokens=original_tokens,
                        used_tokens=0,
                        score=memory.score,
                        preview=_preview(memory.content),
                    )
                )
                continue

            result = self.compressor.compress(
                memory.content,
                token_budget=target,
                query=query,
            )
            if not result.text:
                status = "excluded"
                reason = "memory_budget_exhausted"
                used_tokens = 0
            else:
                included.append(
                    memory.model_copy(
                        update={"content": result.text},
                    )
                )
                remaining -= result.used_tokens
                status = "compressed" if result.compressed else "included"
                reason = (
                    "compressed_by_relevance_budget"
                    if result.compressed
                    else "relevant_memory"
                )
                used_tokens = result.used_tokens

            decisions.append(
                ContextDecision(
                    component_id=f"memory:{memory.id}",
                    kind="memory",
                    label=str(memory.id),
                    status=status,
                    reason=reason,
                    priority=80,
                    original_tokens=original_tokens,
                    used_tokens=used_tokens,
                    score=memory.score,
                    preview=_preview(result.text or memory.content),
                )
            )

        return included, decisions

    def _fit_skills(
        self,
        *,
        candidates: list[SkillContextItem],
        query: str,
        granted_permissions: set[str],
        budget: int,
        skill_limit: int,
        fallback_skill_count: int,
    ) -> tuple[list[str], list[ContextDecision]]:
        selection = self.selector.rank(
            query=query,
            candidates=candidates,
            granted_permissions=granted_permissions,
        )
        decisions: list[ContextDecision] = []

        for skill in selection.permission_filtered:
            decisions.append(
                ContextDecision(
                    component_id=f"skill:{skill.name}",
                    kind="skill",
                    label=skill.name,
                    status="excluded",
                    reason="permission_filtered",
                    priority=70,
                    original_tokens=self._skill_tokens(skill),
                    used_tokens=0,
                    preview=_preview(skill.description),
                )
            )

        relevant = [
            ranked
            for ranked in selection.ranked
            if ranked.score > 0
        ]
        if relevant:
            planned = relevant[:skill_limit]
        else:
            planned = [
                ranked
                for ranked in selection.ranked
                if ranked.skill.side_effect == "READ_ONLY"
            ][: min(skill_limit, fallback_skill_count)]

        planned_names = {item.skill.name for item in planned}
        selected_names: list[str] = []
        remaining = budget

        for ranked in selection.ranked:
            skill = ranked.skill
            tokens = self._skill_tokens(skill)

            if skill.name not in planned_names:
                reason = (
                    "skill_limit_or_low_relevance"
                    if relevant
                    else "not_selected_as_safe_fallback"
                )
                decisions.append(
                    ContextDecision(
                        component_id=f"skill:{skill.name}",
                        kind="skill",
                        label=skill.name,
                        status="excluded",
                        reason=reason,
                        priority=70,
                        original_tokens=tokens,
                        used_tokens=0,
                        score=ranked.score,
                        preview=_preview(skill.description),
                    )
                )
                continue

            if tokens > remaining:
                decisions.append(
                    ContextDecision(
                        component_id=f"skill:{skill.name}",
                        kind="skill",
                        label=skill.name,
                        status="excluded",
                        reason="skill_token_budget_exhausted",
                        priority=70,
                        original_tokens=tokens,
                        used_tokens=0,
                        score=ranked.score,
                        preview=_preview(skill.description),
                    )
                )
                continue

            selected_names.append(skill.name)
            remaining -= tokens
            decisions.append(
                ContextDecision(
                    component_id=f"skill:{skill.name}",
                    kind="skill",
                    label=skill.name,
                    status="included",
                    reason=ranked.reason,
                    priority=70,
                    original_tokens=tokens,
                    used_tokens=tokens,
                    score=ranked.score,
                    preview=_preview(skill.description),
                )
            )

        return sorted(selected_names), decisions

    def _skill_tokens(self, skill: SkillContextItem) -> int:
        return self.estimator.estimate_tool(
            ModelToolDefinition(
                name=skill.name,
                description=skill.description,
                parameters=dict(skill.input_schema),
            )
        )

    @staticmethod
    def _selected_tool_definitions(
        *,
        skill_candidates: list[SkillContextItem],
        selected_names: set[str],
    ) -> list[ModelToolDefinition]:
        return [
            ModelToolDefinition(
                name=skill.name,
                description=skill.description,
                parameters=dict(skill.input_schema),
            )
            for skill in skill_candidates
            if skill.name in selected_names
        ]

    @staticmethod
    def _policy_dict(policy: ContextPolicy) -> dict[str, int]:
        return {
            "context_window_tokens": policy.context_window_tokens,
            "reserved_output_tokens": policy.reserved_output_tokens,
            "runtime_reserve_tokens": policy.runtime_reserve_tokens,
            "additional_context_tokens": policy.additional_context_tokens,
            "memory_tokens": policy.memory_tokens,
            "skill_tokens": policy.skill_tokens,
            "skill_limit": policy.skill_limit,
            "item_max_tokens": policy.item_max_tokens,
            "fallback_skill_count": policy.fallback_skill_count,
        }

    @staticmethod
    def _resolve_policy(
        raw: dict[str, Any],
        *,
        model_max_tokens: int | None,
    ) -> ContextPolicy:
        return resolve_context_policy(
            raw,
            default_context_window_tokens=settings.context_token_budget,
            default_reserved_output_tokens=settings.context_reserved_output_tokens,
            default_runtime_reserve_tokens=settings.context_runtime_reserve_tokens,
            default_additional_context_tokens=settings.context_additional_tokens,
            default_memory_tokens=settings.context_memory_tokens,
            default_skill_tokens=settings.context_skill_tokens,
            default_skill_limit=settings.context_skill_limit,
            default_item_max_tokens=settings.context_item_max_tokens,
            default_fallback_skill_count=settings.context_fallback_skill_count,
            model_max_tokens=model_max_tokens,
        )
