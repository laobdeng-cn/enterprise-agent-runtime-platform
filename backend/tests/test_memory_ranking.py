from datetime import UTC, datetime, timedelta

from app.memory.contracts import MemoryScope
from app.memory.ranking import memory_relevance_score, tokenize_memory_text


def test_memory_tokenizer_handles_english_and_cjk() -> None:
    tokens = tokenize_memory_text("Python 数据分析 Agent")

    assert "python" in tokens
    assert "数" in tokens
    assert "数据" in tokens
    assert "agent" in tokens


def test_relevant_run_memory_scores_above_unrelated_user_memory() -> None:
    now = datetime.now(UTC)

    relevant = memory_relevance_score(
        query="Python data analysis",
        content="Use Python for data analysis and report generation.",
        importance=0.8,
        scope=MemoryScope.RUN,
        updated_at=now,
        now=now,
    )
    unrelated = memory_relevance_score(
        query="Python data analysis",
        content="The preferred office meeting room is on floor three.",
        importance=0.8,
        scope=MemoryScope.USER,
        updated_at=now - timedelta(days=90),
        now=now,
    )

    assert relevant > unrelated
    assert relevant > 0.4
