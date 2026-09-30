import re
from datetime import UTC, datetime

from app.memory.contracts import MemoryScope

_LATIN_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)
_CJK_RE = re.compile(r"[\u3400-\u9fff]")


def tokenize_memory_text(value: str) -> set[str]:
    lowered = value.casefold()
    tokens = {
        match.group(0)
        for match in _LATIN_TOKEN_RE.finditer(lowered)
    }

    cjk = _CJK_RE.findall(lowered)
    tokens.update(cjk)
    tokens.update(
        "".join(cjk[index : index + 2])
        for index in range(max(0, len(cjk) - 1))
    )
    return {token for token in tokens if token}


def memory_relevance_score(
    *,
    query: str,
    content: str,
    importance: float,
    scope: MemoryScope,
    updated_at: datetime,
    now: datetime | None = None,
) -> float:
    reference_time = now or datetime.now(UTC)
    updated = (
        updated_at.replace(tzinfo=UTC)
        if updated_at.tzinfo is None
        else updated_at
    )
    age_days = max(
        0.0,
        (reference_time - updated).total_seconds() / 86400.0,
    )
    recency = 1.0 / (1.0 + age_days / 30.0)
    scope_weight = {
        MemoryScope.RUN: 1.0,
        MemoryScope.AGENT: 0.65,
        MemoryScope.USER: 0.35,
    }[scope]

    query_tokens = tokenize_memory_text(query)
    content_tokens = tokenize_memory_text(content)

    if not query_tokens:
        return min(
            1.0,
            importance * 0.65 + recency * 0.25 + scope_weight * 0.10,
        )

    overlap = query_tokens & content_tokens
    coverage = len(overlap) / max(1, len(query_tokens))
    union = query_tokens | content_tokens
    jaccard = len(overlap) / max(1, len(union))
    phrase = 1.0 if query.casefold().strip() in content.casefold() else 0.0

    score = (
        coverage * 0.52
        + jaccard * 0.12
        + phrase * 0.08
        + importance * 0.16
        + recency * 0.07
        + scope_weight * 0.05
    )
    return min(1.0, max(0.0, score))
