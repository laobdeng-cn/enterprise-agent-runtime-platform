from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from common.security import internal_transport_security

mcp = MCPServer(
    "Experiment Data",
    version="0.10.0",
)

EXPERIMENTS: list[dict[str, Any]] = [
    {
        "id": "exp-2026-041",
        "title": "Perovskite annealing baseline",
        "material": "perovskite",
        "objective": "Establish baseline efficiency around 105 C annealing.",
        "parameters": {
            "annealing_c": 105,
            "humidity_pct": 28,
            "spin_rpm": 4200,
        },
        "metrics": {
            "efficiency_pct": 22.1,
            "yield_pct": 91.0,
        },
        "status": "completed",
        "created_at": "2026-06-11T09:00:00+00:00",
    },
    {
        "id": "exp-2026-052",
        "title": "High-temperature stress run",
        "material": "perovskite",
        "objective": "Measure process sensitivity above baseline temperature.",
        "parameters": {
            "annealing_c": 116,
            "humidity_pct": 29,
            "spin_rpm": 4200,
        },
        "metrics": {
            "efficiency_pct": 19.4,
            "yield_pct": 77.0,
        },
        "status": "completed",
        "created_at": "2026-07-02T09:00:00+00:00",
    },
    {
        "id": "exp-2026-061",
        "title": "Humidity sensitivity run",
        "material": "perovskite",
        "objective": "Measure humidity sensitivity at baseline temperature.",
        "parameters": {
            "annealing_c": 105,
            "humidity_pct": 43,
            "spin_rpm": 4200,
        },
        "metrics": {
            "efficiency_pct": 20.0,
            "yield_pct": 81.0,
        },
        "status": "completed",
        "created_at": "2026-08-09T09:00:00+00:00",
    },
]


@mcp.tool()
def search_experiments(
    query: str = "",
    material: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search authorized experiment records."""
    bounded = max(1, min(50, int(limit)))
    query_lower = query.casefold().strip()
    material_lower = material.casefold().strip() if material else None

    matches: list[dict[str, Any]] = []
    for item in reversed(EXPERIMENTS):
        if material_lower and str(item["material"]).casefold() != material_lower:
            continue
        if query_lower:
            haystack = (
                f"{item['title']} {item['objective']} "
                f"{item['material']} {item['parameters']}"
            ).casefold()
            if query_lower not in haystack:
                continue
        matches.append(dict(item))
        if len(matches) >= bounded:
            break

    return {
        "query": query,
        "material": material,
        "count": len(matches),
        "experiments": matches,
    }


@mcp.tool()
def get_experiment(experiment_id: str) -> dict[str, Any]:
    """Read one authorized experiment record."""
    for item in EXPERIMENTS:
        if item["id"] == experiment_id:
            return dict(item)
    raise ValueError(f"Experiment '{experiment_id}' was not found")


@mcp.tool()
def create_experiment(
    title: str,
    material: str,
    objective: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Create a candidate experiment record in the enterprise R&D system."""
    record = {
        "id": f"exp-{uuid4().hex[:12]}",
        "title": title,
        "material": material,
        "objective": objective,
        "parameters": dict(parameters),
        "metrics": {},
        "status": "planned",
        "created_at": datetime.now(UTC).isoformat(),
    }
    EXPERIMENTS.append(record)
    return dict(record)


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> Response:
    return JSONResponse(
        {
            "status": "ok",
            "service": "experiment-mcp",
            "experiments": len(EXPERIMENTS),
        }
    )


app = mcp.streamable_http_app(
    transport_security=internal_transport_security("experiment-mcp"),
)
