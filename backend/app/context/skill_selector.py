import re
from dataclasses import dataclass

from app.agents.harness.contracts import SkillContextItem

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]")


@dataclass(frozen=True, slots=True)
class RankedSkill:
    skill: SkillContextItem
    score: float
    reason: str


@dataclass(frozen=True, slots=True)
class SkillSelection:
    ranked: list[RankedSkill]
    permission_filtered: list[SkillContextItem]


def _tokens(value: str) -> set[str]:
    tokens = {
        match.group(0).casefold()
        for match in _TOKEN_RE.finditer(value)
        if match.group(0).strip()
    }
    expanded = set(tokens)
    if "+" in value:
        expanded.update({"add", "sum", "math"})
    if "calculate" in expanded or "calculation" in expanded:
        expanded.update({"math", "add"})
    if "search" in expanded or "find" in expanded:
        expanded.update({"query", "read"})
    if "report" in expanded:
        expanded.update({"artifact", "write", "document"})
    return expanded


class SkillSelector:
    """Ranks bound Skills while keeping authorization outside the LLM."""

    def rank(
        self,
        *,
        query: str,
        candidates: list[SkillContextItem],
        granted_permissions: set[str],
    ) -> SkillSelection:
        query_tokens = _tokens(query)
        eligible: list[RankedSkill] = []
        permission_filtered: list[SkillContextItem] = []

        for skill in candidates:
            required = set(skill.required_permissions)
            if not required.issubset(granted_permissions):
                permission_filtered.append(skill)
                continue

            skill_text = " ".join(
                [
                    skill.name.replace("_", " "),
                    skill.description,
                    " ".join(skill.input_schema.get("properties", {}).keys())
                    if isinstance(
                        skill.input_schema.get("properties"),
                        dict,
                    )
                    else "",
                ]
            )
            skill_tokens = _tokens(skill_text)
            overlap = query_tokens & skill_tokens
            coverage = len(overlap) / max(1, len(query_tokens))
            jaccard = len(overlap) / max(1, len(query_tokens | skill_tokens))
            exact_name = (
                1.0
                if skill.name.casefold() in query.casefold()
                else 0.0
            )
            score = coverage * 0.68 + jaccard * 0.22 + exact_name * 0.10

            if score > 0:
                reason = "query_relevance"
            elif skill.side_effect == "READ_ONLY":
                reason = "safe_fallback"
            else:
                reason = "fallback"

            eligible.append(
                RankedSkill(
                    skill=skill,
                    score=score,
                    reason=reason,
                )
            )

        eligible.sort(
            key=lambda item: (
                item.score > 0,
                item.score,
                item.skill.side_effect == "READ_ONLY",
                item.skill.name,
            ),
            reverse=True,
        )
        return SkillSelection(
            ranked=eligible,
            permission_filtered=permission_filtered,
        )


skill_selector = SkillSelector()
