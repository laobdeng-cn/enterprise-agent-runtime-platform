import pytest

from app.runtime.state_machine import (
    InvalidRunTransitionError,
    RunState,
    ensure_transition,
    is_terminal,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RunState.PENDING, RunState.RUNNING),
        (RunState.PENDING, RunState.CANCELLED),
        (RunState.RUNNING, RunState.PAUSED),
        (RunState.RUNNING, RunState.RETRYING),
        (RunState.RUNNING, RunState.COMPLETED),
        (RunState.RETRYING, RunState.RUNNING),
        (RunState.RETRYING, RunState.PAUSED),
        (RunState.PAUSED, RunState.RUNNING),
        (RunState.PAUSED, RunState.CANCELLED),
    ],
)
def test_valid_run_transitions(current: RunState, target: RunState) -> None:
    ensure_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RunState.COMPLETED, RunState.RUNNING),
        (RunState.FAILED, RunState.RUNNING),
        (RunState.CANCELLED, RunState.RUNNING),
        (RunState.PENDING, RunState.COMPLETED),
        (RunState.PAUSED, RunState.COMPLETED),
    ],
)
def test_invalid_run_transitions(current: RunState, target: RunState) -> None:
    with pytest.raises(InvalidRunTransitionError):
        ensure_transition(current, target)


def test_terminal_state_detection() -> None:
    assert is_terminal(RunState.COMPLETED)
    assert is_terminal("FAILED")
    assert is_terminal("CANCELLED")
    assert not is_terminal("PAUSED")
