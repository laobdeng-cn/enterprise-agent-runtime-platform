import uuid

import pytest

from app.agents.harness.context import ContextBuilder
from app.agents.harness.contracts import (
    MemoryContextItem,
    ModelMessage,
    SkillContextItem,
)
from app.context.budget import ContextBudgetExceededError


def test_context_builder_preserves_authoritative_input_and_compresses_context() -> None:
    builder = ContextBuilder()
    additional = (
        "Background filler sentence. " * 180
        + "The report must compare quarterly latency and error rate."
    )
    memory = MemoryContextItem(
        id=uuid.uuid4(),
        memory_type="LONG_TERM",
        scope="USER",
        content="Prefer concise Markdown reports with explicit evidence.",
        score=0.91,
        importance=0.8,
        source="USER",
    )

    package = builder.build(
        system_instructions="Never bypass enterprise authorization.",
        user_input="Prepare the quarterly latency report.",
        additional_context=[additional],
        relevant_memory=[memory],
        context_policy={
            "context_window_tokens": 4096,
            "reserved_output_tokens": 512,
            "runtime_reserve_tokens": 512,
            "additional_context_tokens": 256,
            "memory_tokens": 256,
            "skill_tokens": 256,
            "item_max_tokens": 128,
        },
        model_max_tokens=256,
    )

    messages = package.to_messages()
    assert messages[0].content == "Never bypass enterprise authorization."
    assert messages[-1].content == "Prepare the quarterly latency report."
    assert package.trace.budget.used_tokens <= package.trace.budget.initial_budget_tokens
    assert package.trace.compression_count >= 1
    assert any(
        item.kind == "additional_context" and item.status == "compressed"
        for item in package.trace.decisions
    )


def test_context_builder_selects_relevant_authorized_skills_only() -> None:
    builder = ContextBuilder()
    skills = [
        SkillContextItem(
            name="math_add",
            description="Add two numeric values.",
            input_schema={
                "type": "object",
                "properties": {
                    "left": {"type": "number"},
                    "right": {"type": "number"},
                },
            },
            required_permissions=["skill:execute"],
            side_effect="READ_ONLY",
        ),
        SkillContextItem(
            name="admin_delete",
            description="Delete platform data.",
            input_schema={"type": "object", "properties": {}},
            required_permissions=["skill:execute", "admin:manage"],
            side_effect="IRREVERSIBLE_WRITE",
        ),
        SkillContextItem(
            name="workspace_read_text",
            description="Read text from the current workspace.",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
            required_permissions=["skill:execute", "workspace:read"],
            side_effect="READ_ONLY",
        ),
    ]

    package = builder.build(
        system_instructions="Use authorized capabilities only.",
        user_input="Add 2 and 3.",
        skill_candidates=skills,
        granted_permissions={"skill:execute", "workspace:read"},
        context_policy={
            "context_window_tokens": 4096,
            "reserved_output_tokens": 512,
            "runtime_reserve_tokens": 512,
            "skill_tokens": 1000,
            "skill_limit": 2,
            "fallback_skill_count": 1,
        },
        model_max_tokens=256,
    )

    assert "math_add" in package.selected_skill_names
    assert "admin_delete" not in package.selected_skill_names
    denied = next(
        item
        for item in package.trace.decisions
        if item.component_id == "skill:admin_delete"
    )
    assert denied.reason == "permission_filtered"


def test_runtime_tool_history_is_compressed_inside_input_budget() -> None:
    builder = ContextBuilder()
    messages = [
        ModelMessage(role="system", content="System policy."),
        ModelMessage(role="user", content="Analyze the tool result."),
        ModelMessage(
            role="tool",
            tool_call_id="call-1",
            content="large tool output " * 700,
        ),
    ]

    fitted, metadata = builder.fit_runtime_messages(
        messages=messages,
        tools=[],
        input_budget_tokens=220,
    )

    assert metadata["compressed_tool_messages"] == 1
    assert metadata["used_tokens"] <= 220
    assert fitted[-1].content is not None
    assert "compressed tool result" in fitted[-1].content


def test_authoritative_context_is_never_silently_truncated() -> None:
    builder = ContextBuilder()

    with pytest.raises(ContextBudgetExceededError):
        builder.build(
            system_instructions="policy " * 5000,
            user_input="current request",
            context_policy={
                "context_window_tokens": 4096,
                "reserved_output_tokens": 512,
                "runtime_reserve_tokens": 512,
            },
            model_max_tokens=256,
        )
