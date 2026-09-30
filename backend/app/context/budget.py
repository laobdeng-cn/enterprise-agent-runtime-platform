from dataclasses import dataclass
from typing import Any


class ContextPolicyError(ValueError):
    pass


class ContextBudgetExceededError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ContextPolicy:
    context_window_tokens: int
    reserved_output_tokens: int
    runtime_reserve_tokens: int
    additional_context_tokens: int
    memory_tokens: int
    skill_tokens: int
    skill_limit: int
    item_max_tokens: int
    fallback_skill_count: int

    @property
    def input_budget_tokens(self) -> int:
        return self.context_window_tokens - self.reserved_output_tokens

    @property
    def initial_budget_tokens(self) -> int:
        return self.input_budget_tokens - self.runtime_reserve_tokens


def _int_value(
    source: dict[str, Any],
    key: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw = source.get(key, default)
    if isinstance(raw, bool):
        raise ContextPolicyError(f"{key} must be an integer")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ContextPolicyError(f"{key} must be an integer") from exc
    if value < minimum or value > maximum:
        raise ContextPolicyError(
            f"{key} must be between {minimum} and {maximum}"
        )
    return value


def resolve_context_policy(
    raw: dict[str, Any],
    *,
    default_context_window_tokens: int,
    default_reserved_output_tokens: int,
    default_runtime_reserve_tokens: int,
    default_additional_context_tokens: int,
    default_memory_tokens: int,
    default_skill_tokens: int,
    default_skill_limit: int,
    default_item_max_tokens: int,
    default_fallback_skill_count: int,
    model_max_tokens: int | None,
) -> ContextPolicy:
    context_window = _int_value(
        raw,
        "context_window_tokens",
        default_context_window_tokens,
        minimum=4096,
        maximum=262144,
    )
    configured_reserved = _int_value(
        raw,
        "reserved_output_tokens",
        default_reserved_output_tokens,
        minimum=256,
        maximum=65536,
    )
    reserved_output = max(
        configured_reserved,
        min(model_max_tokens or 0, 65536),
    )
    if reserved_output >= context_window - 1024:
        raise ContextPolicyError(
            "reserved_output_tokens must leave at least 1024 input tokens"
        )

    runtime_reserve = _int_value(
        raw,
        "runtime_reserve_tokens",
        default_runtime_reserve_tokens,
        minimum=256,
        maximum=32768,
    )
    if runtime_reserve >= context_window - reserved_output - 512:
        raise ContextPolicyError(
            "runtime_reserve_tokens leaves insufficient initial context budget"
        )

    return ContextPolicy(
        context_window_tokens=context_window,
        reserved_output_tokens=reserved_output,
        runtime_reserve_tokens=runtime_reserve,
        additional_context_tokens=_int_value(
            raw,
            "additional_context_tokens",
            default_additional_context_tokens,
            minimum=0,
            maximum=65536,
        ),
        memory_tokens=_int_value(
            raw,
            "memory_tokens",
            default_memory_tokens,
            minimum=0,
            maximum=65536,
        ),
        skill_tokens=_int_value(
            raw,
            "skill_tokens",
            default_skill_tokens,
            minimum=0,
            maximum=32768,
        ),
        skill_limit=_int_value(
            raw,
            "skill_limit",
            default_skill_limit,
            minimum=0,
            maximum=32,
        ),
        item_max_tokens=_int_value(
            raw,
            "item_max_tokens",
            default_item_max_tokens,
            minimum=64,
            maximum=16384,
        ),
        fallback_skill_count=_int_value(
            raw,
            "fallback_skill_count",
            default_fallback_skill_count,
            minimum=0,
            maximum=8,
        ),
    )
