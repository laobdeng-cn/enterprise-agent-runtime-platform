import uuid

from app.runtime.orchestration import RuntimeThread


def test_runtime_thread_maps_run_to_stable_graph_identity() -> None:
    run_id = uuid.uuid4()
    config = RuntimeThread(run_id).graph_config()

    assert config == {
        "configurable": {
            "thread_id": str(run_id),
            "checkpoint_ns": "agent-runtime",
        }
    }
