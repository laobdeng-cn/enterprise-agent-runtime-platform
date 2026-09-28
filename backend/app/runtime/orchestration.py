from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RuntimeThread:
    """Stable mapping between a domain Run and graph-engine thread identity."""

    run_id: UUID

    def graph_config(self) -> dict[str, Any]:
        return {
            "configurable": {
                "thread_id": str(self.run_id),
                "checkpoint_ns": "agent-runtime",
            }
        }
