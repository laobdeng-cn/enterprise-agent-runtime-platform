import pytest

from app.workflows.graph import (
    WorkflowGraphError,
    evaluate_condition,
    execution_waves,
)


def test_execution_waves_support_controlled_parallel_branches() -> None:
    waves = execution_waves(
        {
            "plan": [],
            "research": ["plan"],
            "analysis": ["plan"],
            "review": ["research", "analysis"],
        }
    )

    assert waves == [
        ["plan"],
        ["analysis", "research"],
        ["review"],
    ]


def test_execution_waves_reject_cycle() -> None:
    with pytest.raises(WorkflowGraphError, match="cycle"):
        execution_waves(
            {
                "plan": ["review"],
                "review": ["plan"],
            }
        )


def test_execution_waves_reject_unknown_dependency() -> None:
    with pytest.raises(WorkflowGraphError, match="unknown"):
        execution_waves(
            {
                "plan": [],
                "review": ["missing"],
            }
        )


def test_condition_routes_from_workflow_input() -> None:
    assert evaluate_condition(
        {
            "source": "workflow_input",
            "path": "mode",
            "op": "equals",
            "value": "deep",
        },
        workflow_input={"mode": "deep"},
        node_outputs={},
    )


def test_condition_routes_from_dependency_output() -> None:
    assert evaluate_condition(
        {
            "source": "node_output",
            "node": "planner",
            "path": "result.approved",
            "op": "equals",
            "value": True,
        },
        workflow_input={},
        node_outputs={
            "planner": {
                "result": {
                    "approved": True,
                }
            }
        },
    )
