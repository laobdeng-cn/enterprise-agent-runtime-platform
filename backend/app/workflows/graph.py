from graphlib import CycleError, TopologicalSorter
from typing import Any


class WorkflowGraphError(ValueError):
    pass


def execution_waves(
    dependencies: dict[str, list[str]],
) -> list[list[str]]:
    if not dependencies:
        raise WorkflowGraphError("Workflow must contain at least one node")
    keys = set(dependencies)
    for key, values in dependencies.items():
        if key in values:
            raise WorkflowGraphError(f"Node '{key}' cannot depend on itself")
        missing = set(values) - keys
        if missing:
            raise WorkflowGraphError(
                f"Node '{key}' depends on unknown node(s): "
                + ", ".join(sorted(missing))
            )

    sorter = TopologicalSorter(dependencies)
    try:
        sorter.prepare()
    except CycleError as exc:
        raise WorkflowGraphError("Workflow graph contains a cycle") from exc

    waves: list[list[str]] = []
    while sorter.is_active():
        ready = sorted(sorter.get_ready())
        if not ready:
            raise WorkflowGraphError("Workflow graph cannot make progress")
        waves.append(ready)
        sorter.done(*ready)
    return waves


def _path(value: Any, dotted: str) -> Any:
    current = value
    for part in filter(None, dotted.split(".")):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def evaluate_condition(
    condition: dict[str, Any],
    *,
    workflow_input: dict[str, Any],
    node_outputs: dict[str, dict[str, Any]],
) -> bool:
    if not condition:
        return True

    source = str(condition.get("source", "workflow_input"))
    if source == "workflow_input":
        root: Any = workflow_input
    elif source == "node_output":
        node_key = str(condition.get("node", ""))
        if not node_key:
            raise WorkflowGraphError(
                "node_output condition requires 'node'"
            )
        root = node_outputs.get(node_key)
    else:
        raise WorkflowGraphError(
            f"Unsupported condition source '{source}'"
        )

    actual = _path(root, str(condition.get("path", "")))
    op = str(condition.get("op", "truthy"))
    expected = condition.get("value")

    if op == "exists":
        return actual is not None
    if op == "truthy":
        return bool(actual)
    if op == "falsy":
        return not bool(actual)
    if op == "equals":
        return actual == expected
    if op == "not_equals":
        return actual != expected
    if op == "contains":
        return isinstance(actual, (str, list, tuple, dict)) and expected in actual
    raise WorkflowGraphError(f"Unsupported condition operator '{op}'")
