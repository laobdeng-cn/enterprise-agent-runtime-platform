from enum import StrEnum


class RunState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    PAUSED = "PAUSED"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES = {
    RunState.COMPLETED,
    RunState.FAILED,
    RunState.CANCELLED,
}

_ALLOWED_TRANSITIONS: dict[RunState, set[RunState]] = {
    RunState.PENDING: {
        RunState.RUNNING,
        RunState.CANCELLED,
    },
    RunState.RUNNING: {
        RunState.WAITING_APPROVAL,
        RunState.PAUSED,
        RunState.RETRYING,
        RunState.COMPLETED,
        RunState.FAILED,
        RunState.CANCELLED,
    },
    RunState.WAITING_APPROVAL: {
        RunState.RUNNING,
        RunState.FAILED,
        RunState.CANCELLED,
    },
    RunState.PAUSED: {
        RunState.RUNNING,
        RunState.CANCELLED,
    },
    RunState.RETRYING: {
        RunState.RUNNING,
        RunState.PAUSED,
        RunState.FAILED,
        RunState.CANCELLED,
    },
    RunState.COMPLETED: set(),
    RunState.FAILED: set(),
    RunState.CANCELLED: set(),
}


class InvalidRunTransitionError(ValueError):
    pass


def parse_run_state(value: str) -> RunState:
    try:
        return RunState(value)
    except ValueError as exc:
        raise InvalidRunTransitionError(
            f"Unknown Run state '{value}'"
        ) from exc


def ensure_transition(current: RunState, target: RunState) -> None:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidRunTransitionError(
            f"Invalid Run transition: {current.value} -> {target.value}"
        )


def is_terminal(state: RunState | str) -> bool:
    parsed = state if isinstance(state, RunState) else parse_run_state(state)
    return parsed in TERMINAL_STATES
