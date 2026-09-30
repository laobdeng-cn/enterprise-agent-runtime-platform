import json
import math
import re
from typing import Any

from app.agents.harness.contracts import ModelMessage, ModelToolDefinition

_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


class TokenEstimator:
    """Deterministic provider-independent token estimator.

    It intentionally estimates instead of claiming provider tokenizer parity.
    The estimate is conservative enough for platform-side budgeting and remains
    stable in CI without introducing a provider-specific tokenizer dependency.
    """

    message_overhead_tokens: int = 4
    tool_overhead_tokens: int = 12

    def estimate_text(self, text: str | None) -> int:
        if not text:
            return 0

        cjk = len(_CJK_RE.findall(text))
        latin_words = len(_LATIN_WORD_RE.findall(text))
        punctuation = len(_PUNCT_RE.findall(text))

        latin_chars = sum(
            len(match.group(0))
            for match in _LATIN_WORD_RE.finditer(text)
        )
        long_word_adjustment = max(
            0,
            math.ceil(latin_chars / 4) - latin_words,
        )

        whitespace_adjustment = max(0, text.count("\n") // 2)
        return max(
            1,
            cjk
            + latin_words
            + long_word_adjustment
            + math.ceil(punctuation * 0.35)
            + whitespace_adjustment,
        )

    def estimate_json(self, value: Any) -> int:
        return self.estimate_text(
            json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
                default=str,
            )
        )

    def estimate_message(self, message: ModelMessage) -> int:
        total = self.message_overhead_tokens
        total += self.estimate_text(message.role)
        total += self.estimate_text(message.content)
        total += self.estimate_text(message.tool_call_id)
        if message.tool_calls:
            total += self.estimate_json(
                [call.model_dump(mode="json") for call in message.tool_calls]
            )
        return total

    def estimate_messages(self, messages: list[ModelMessage]) -> int:
        return sum(self.estimate_message(message) for message in messages)

    def estimate_tool(self, tool: ModelToolDefinition) -> int:
        return (
            self.tool_overhead_tokens
            + self.estimate_text(tool.name)
            + self.estimate_text(tool.description)
            + self.estimate_json(tool.parameters)
        )

    def estimate_tools(self, tools: list[ModelToolDefinition]) -> int:
        return sum(self.estimate_tool(tool) for tool in tools)


token_estimator = TokenEstimator()
