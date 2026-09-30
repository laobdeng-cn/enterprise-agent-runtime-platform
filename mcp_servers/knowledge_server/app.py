from typing import Any

from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from common.security import internal_transport_security

mcp = MCPServer(
    "Enterprise Knowledge",
    version="0.10.0",
)

DOCUMENTS: list[dict[str, Any]] = [
    {
        "id": "kb-perovskite-001",
        "title": "Perovskite thin-film process window",
        "tags": ["perovskite", "thin-film", "annealing"],
        "content": (
            "Internal process note: film uniformity degraded when annealing "
            "temperature exceeded 112 C under the current solvent system. "
            "Recommended screening window is 98-110 C."
        ),
    },
    {
        "id": "kb-encapsulation-002",
        "title": "Encapsulation humidity guideline",
        "tags": ["encapsulation", "humidity", "stability"],
        "content": (
            "Pilot-line guideline: encapsulation steps should begin below "
            "35 percent relative humidity. Higher humidity correlated with "
            "shorter stability-test lifetime."
        ),
    },
    {
        "id": "kb-qc-003",
        "title": "R&D quality review checklist",
        "tags": ["quality", "review", "experiment"],
        "content": (
            "Every candidate experiment should include a baseline, parameter "
            "diff, measurement method, expected outcome, and rollback note."
        ),
    },
]


def _score(document: dict[str, Any], query: str) -> int:
    terms = {
        term.casefold()
        for term in query.replace(",", " ").split()
        if term.strip()
    }
    haystack = " ".join(
        [
            str(document["title"]),
            " ".join(str(tag) for tag in document["tags"]),
            str(document["content"]),
        ]
    ).casefold()
    return sum(1 for term in terms if term in haystack)


@mcp.tool()
def search_documents(query: str, limit: int = 5) -> dict[str, Any]:
    """Search approved internal knowledge documents."""
    bounded = max(1, min(20, int(limit)))
    ranked = sorted(
        DOCUMENTS,
        key=lambda item: (_score(item, query), item["id"]),
        reverse=True,
    )
    matches = [
        {
            "id": item["id"],
            "title": item["title"],
            "tags": item["tags"],
            "snippet": item["content"][:220],
            "score": _score(item, query),
        }
        for item in ranked
        if _score(item, query) > 0
    ][:bounded]
    return {
        "query": query,
        "count": len(matches),
        "matches": matches,
    }


@mcp.tool()
def get_document(document_id: str) -> dict[str, Any]:
    """Read one approved internal knowledge document by id."""
    for item in DOCUMENTS:
        if item["id"] == document_id:
            return dict(item)
    raise ValueError(f"Document '{document_id}' was not found")


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> Response:
    return JSONResponse(
        {
            "status": "ok",
            "service": "knowledge-mcp",
            "documents": len(DOCUMENTS),
        }
    )


app = mcp.streamable_http_app(
    transport_security=internal_transport_security("knowledge-mcp"),
)
