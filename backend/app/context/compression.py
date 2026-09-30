import re
from dataclasses import dataclass

from app.context.tokenizer import TokenEstimator, token_estimator

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+|\n+")
_WORD_RE = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]")


@dataclass(frozen=True, slots=True)
class CompressionResult:
    text: str
    original_tokens: int
    used_tokens: int
    compressed: bool


def _query_terms(query: str) -> set[str]:
    return {
        match.group(0).casefold()
        for match in _WORD_RE.finditer(query)
        if match.group(0).strip()
    }


class ContextCompressor:
    """Deterministic extractive compressor for non-authoritative context."""

    def __init__(self, estimator: TokenEstimator | None = None) -> None:
        self.estimator = estimator or token_estimator

    def compress(
        self,
        text: str,
        *,
        token_budget: int,
        query: str = "",
    ) -> CompressionResult:
        original_tokens = self.estimator.estimate_text(text)
        if original_tokens <= token_budget:
            return CompressionResult(
                text=text,
                original_tokens=original_tokens,
                used_tokens=original_tokens,
                compressed=False,
            )

        if token_budget <= 0:
            return CompressionResult(
                text="",
                original_tokens=original_tokens,
                used_tokens=0,
                compressed=True,
            )

        segments = [
            segment.strip()
            for segment in _SENTENCE_SPLIT_RE.split(text)
            if segment.strip()
        ]
        if not segments:
            return self._truncate(
                text,
                token_budget=token_budget,
                original_tokens=original_tokens,
            )

        query_terms = _query_terms(query)
        ranked: list[tuple[float, int, str]] = []
        for index, segment in enumerate(segments):
            terms = _query_terms(segment)
            overlap = len(query_terms & terms)
            coverage = overlap / max(1, len(query_terms))
            first_bonus = 0.18 if index == 0 else 0.0
            last_bonus = 0.08 if index == len(segments) - 1 else 0.0
            score = coverage + first_bonus + last_bonus
            ranked.append((score, index, segment))

        ranked.sort(key=lambda item: (item[0], -item[1]), reverse=True)

        selected: list[tuple[int, str]] = []
        used = 0
        for _, index, segment in ranked:
            segment_tokens = self.estimator.estimate_text(segment)
            separator_tokens = 1 if selected else 0
            if used + segment_tokens + separator_tokens > token_budget:
                continue
            selected.append((index, segment))
            used += segment_tokens + separator_tokens
            if used >= token_budget:
                break

        if not selected:
            return self._truncate(
                text,
                token_budget=token_budget,
                original_tokens=original_tokens,
            )

        selected.sort(key=lambda item: item[0])
        compressed_text = "\n".join(segment for _, segment in selected)
        used_tokens = self.estimator.estimate_text(compressed_text)

        if used_tokens > token_budget:
            return self._truncate(
                compressed_text,
                token_budget=token_budget,
                original_tokens=original_tokens,
            )

        return CompressionResult(
            text=compressed_text,
            original_tokens=original_tokens,
            used_tokens=used_tokens,
            compressed=True,
        )

    def _truncate(
        self,
        text: str,
        *,
        token_budget: int,
        original_tokens: int,
    ) -> CompressionResult:
        if token_budget <= 0:
            return CompressionResult(
                text="",
                original_tokens=original_tokens,
                used_tokens=0,
                compressed=True,
            )

        low = 0
        high = len(text)
        best = ""
        while low <= high:
            middle = (low + high) // 2
            candidate = text[:middle].rstrip()
            tokens = self.estimator.estimate_text(candidate)
            if tokens <= token_budget:
                best = candidate
                low = middle + 1
            else:
                high = middle - 1

        if len(best) < len(text):
            suffix = " …"
            while (
                best
                and self.estimator.estimate_text(best + suffix) > token_budget
            ):
                best = best[:-1].rstrip()
            if best:
                best += suffix

        return CompressionResult(
            text=best,
            original_tokens=original_tokens,
            used_tokens=self.estimator.estimate_text(best),
            compressed=True,
        )


context_compressor = ContextCompressor()
