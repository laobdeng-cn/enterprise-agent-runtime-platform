from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from common.security import internal_transport_security

mcp = MCPServer(
    "Enterprise Operations",
    version="0.10.0",
)

INVENTORY: dict[str, dict[str, Any]] = {
    "perovskite-precursor-a": {
        "sku": "MAT-PER-A",
        "material": "perovskite-precursor-a",
        "available_units": 42,
        "unit": "bottle",
        "location": "R&D-STORE-A",
    },
    "encapsulation-film": {
        "sku": "MAT-ENC-01",
        "material": "encapsulation-film",
        "available_units": 165,
        "unit": "sheet",
        "location": "R&D-STORE-B",
    },
}

WORK_ORDERS: list[dict[str, Any]] = []
APPROVAL_REQUESTS: list[dict[str, Any]] = []


@mcp.tool()
def query_inventory(material: str) -> dict[str, Any]:
    """Query authorized enterprise inventory by material name."""
    key = material.casefold().strip()
    matches = [
        dict(item)
        for name, item in INVENTORY.items()
        if key in name.casefold() or key in str(item["sku"]).casefold()
    ]
    return {
        "query": material,
        "count": len(matches),
        "items": matches,
    }


@mcp.tool()
def create_work_order(
    title: str,
    description: str,
    priority: str = "normal",
    owner_team: str = "materials-rd",
) -> dict[str, Any]:
    """Create a reversible enterprise work-order record."""
    normalized_priority = priority.casefold()
    if normalized_priority not in {"low", "normal", "high", "urgent"}:
        raise ValueError("priority must be low, normal, high, or urgent")

    record = {
        "id": f"wo-{uuid4().hex[:12]}",
        "title": title,
        "description": description,
        "priority": normalized_priority,
        "owner_team": owner_team,
        "status": "open",
        "created_at": datetime.now(UTC).isoformat(),
    }
    WORK_ORDERS.append(record)
    return dict(record)


@mcp.tool()
def submit_approval(
    subject: str,
    reason: str,
    requested_action: str,
) -> dict[str, Any]:
    """Submit an external enterprise approval request."""
    record = {
        "id": f"ap-{uuid4().hex[:12]}",
        "subject": subject,
        "reason": reason,
        "requested_action": requested_action,
        "status": "pending",
        "created_at": datetime.now(UTC).isoformat(),
    }
    APPROVAL_REQUESTS.append(record)
    return dict(record)


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> Response:
    return JSONResponse(
        {
            "status": "ok",
            "service": "enterprise-mcp",
            "inventory_items": len(INVENTORY),
            "work_orders": len(WORK_ORDERS),
            "approvals": len(APPROVAL_REQUESTS),
        }
    )


app = mcp.streamable_http_app(
    transport_security=internal_transport_security("enterprise-mcp"),
)
