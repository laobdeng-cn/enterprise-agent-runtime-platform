from typing import Any

from app.skills.contracts import SkillExecutionContext


async def system_echo(
    arguments: dict[str, Any],
    context: SkillExecutionContext | None = None,
) -> dict[str, Any]:
    return {"text": str(arguments["text"])}


async def math_add(
    arguments: dict[str, Any],
    context: SkillExecutionContext | None = None,
) -> dict[str, Any]:
    left = float(arguments["left"])
    right = float(arguments["right"])
    return {"result": left + right}


async def text_stats(
    arguments: dict[str, Any],
    context: SkillExecutionContext | None = None,
) -> dict[str, Any]:
    text = str(arguments["text"])
    words = [item for item in text.split() if item]
    return {
        "characters": len(text),
        "words": len(words),
        "lines": len(text.splitlines()) if text else 0,
    }


LOCAL_SKILL_HANDLERS = {
    "system_echo": system_echo,
    "math_add": math_add,
    "text_stats": text_stats,
}
