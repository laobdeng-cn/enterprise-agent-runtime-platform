import asyncio
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_maker, engine
from app.models.skill import Skill, SkillVersion

SAFE_SKILLS: dict[str, dict[str, Any]] = {
    "system_echo": {
        "description": "Return the provided text as a structured value.",
        "provider_type": "local",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        "required_permissions": ["skill:execute"],
        "side_effect": "READ_ONLY",
        "provider_config": {"handler": "system_echo"},
    },
    "math_add": {
        "description": "Add two numeric values.",
        "provider_type": "local",
        "input_schema": {
            "type": "object",
            "properties": {
                "left": {"type": "number"},
                "right": {"type": "number"},
            },
            "required": ["left", "right"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {"result": {"type": "number"}},
            "required": ["result"],
            "additionalProperties": False,
        },
        "required_permissions": ["skill:execute"],
        "side_effect": "READ_ONLY",
        "provider_config": {"handler": "math_add"},
    },
    "text_stats": {
        "description": "Calculate character, word, and line counts for text.",
        "provider_type": "local",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "characters": {"type": "integer"},
                "words": {"type": "integer"},
                "lines": {"type": "integer"},
            },
            "required": ["characters", "words", "lines"],
            "additionalProperties": False,
        },
        "required_permissions": ["skill:execute"],
        "side_effect": "READ_ONLY",
        "provider_config": {"handler": "text_stats"},
    },
    "workspace_list": {
        "description": (
            "List files and directories inside this Run's input, working, "
            "or artifacts workspace directories."
        ),
        "provider_type": "workspace",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "minLength": 1}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "name": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": ["file", "directory"],
                            },
                            "size_bytes": {"type": "integer"},
                        },
                        "required": ["path", "name", "type", "size_bytes"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["entries"],
            "additionalProperties": False,
        },
        "required_permissions": ["skill:execute", "workspace:read"],
        "side_effect": "READ_ONLY",
        "provider_config": {"action": "list"},
    },
    "workspace_read_text": {
        "description": (
            "Read a UTF-8 text file from this Run's workspace. "
            "Paths are relative, for example input/task.md or working/result.md."
        ),
        "provider_type": "workspace",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "minLength": 1}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        "required_permissions": ["skill:execute", "workspace:read"],
        "side_effect": "READ_ONLY",
        "provider_config": {"action": "read_text"},
    },
    "workspace_write_text": {
        "description": (
            "Write a UTF-8 text file inside this Run's working directory. "
            "The path must begin with working/."
        ),
        "provider_type": "workspace",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "size_bytes": {"type": "integer"},
                "sha256": {"type": "string"},
            },
            "required": ["path", "size_bytes", "sha256"],
            "additionalProperties": False,
        },
        "required_permissions": ["skill:execute", "workspace:write"],
        "side_effect": "REVERSIBLE_WRITE",
        "provider_config": {"action": "write_text"},
    },
    "artifact_publish": {
        "description": (
            "Publish a file from working/ as an immutable Run artifact "
            "with metadata and a downloadable artifact identity."
        ),
        "provider_type": "workspace",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_path": {"type": "string", "minLength": 1},
                "display_name": {"type": "string", "minLength": 1},
                "kind": {"type": "string", "minLength": 1},
            },
            "required": ["source_path"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "path": {"type": "string"},
                "display_name": {"type": "string"},
                "media_type": {"type": "string"},
                "size_bytes": {"type": "integer"},
                "sha256": {"type": "string"},
            },
            "required": [
                "artifact_id",
                "path",
                "display_name",
                "media_type",
                "size_bytes",
                "sha256",
            ],
            "additionalProperties": False,
        },
        "required_permissions": ["skill:execute", "artifact:create"],
        "side_effect": "REVERSIBLE_WRITE",
        "provider_config": {"action": "publish_artifact"},
    },
,
    "python_execute": {
        "description": (
            "Execute Python 3.12 inside the current Run's isolated Docker sandbox. "
            "Read inputs from /workspace/input or /workspace/working and write "
            "generated files only to /workspace/output."
        ),
        "provider_type": "sandbox",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 100000,
                },
                "publish_artifacts": {"type": "boolean"},
            },
            "required": ["code"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "string"},
                "run_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["SUCCEEDED", "FAILED", "TIMED_OUT"],
                },
                "exit_code": {
                    "anyOf": [
                        {"type": "integer"},
                        {"type": "null"},
                    ]
                },
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
                "duration_ms": {"type": "number"},
                "timed_out": {"type": "boolean"},
                "stdout_truncated": {"type": "boolean"},
                "stderr_truncated": {"type": "boolean"},
                "artifacts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "artifact_id": {"type": "string"},
                            "path": {"type": "string"},
                            "display_name": {"type": "string"},
                            "media_type": {"type": "string"},
                            "size_bytes": {"type": "integer"},
                            "sha256": {"type": "string"},
                        },
                        "required": [
                            "artifact_id",
                            "path",
                            "display_name",
                            "media_type",
                            "size_bytes",
                            "sha256",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": [
                "execution_id",
                "run_id",
                "status",
                "exit_code",
                "stdout",
                "stderr",
                "duration_ms",
                "timed_out",
                "stdout_truncated",
                "stderr_truncated",
                "artifacts",
            ],
            "additionalProperties": False,
        },
        "required_permissions": [
            "skill:execute",
            "sandbox:execute",
            "workspace:read",
            "artifact:create",
        ],
        "side_effect": "REVERSIBLE_WRITE",
        "timeout_seconds": 75,
        "max_attempts": 1,
        "provider_config": {"action": "python_execute"},
    },

async def seed() -> None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Skill).options(
                selectinload(Skill.versions),
                selectinload(Skill.active_version),
            )
        )
        existing = {skill.name: skill for skill in result.scalars().unique().all()}

        for name, definition in SAFE_SKILLS.items():
            skill = existing.get(name)
            provider_type = str(definition["provider_type"])
            if skill is None:
                skill = Skill(
                    name=name,
                    description=str(definition["description"]),
                    provider_type=provider_type,
                    status="active",
                )
                session.add(skill)
                await session.flush()
            else:
                skill.description = str(definition["description"])
                skill.provider_type = provider_type
                skill.status = "active"

            if skill.active_version_id is None:
                version_result = await session.execute(
                    select(func.max(SkillVersion.version)).where(
                        SkillVersion.skill_id == skill.id
                    )
                )
                next_version = (version_result.scalar_one_or_none() or 0) + 1
                version = SkillVersion(
                    skill_id=skill.id,
                    version=next_version,
                    input_schema=dict(definition["input_schema"]),
                    output_schema=dict(definition["output_schema"]),
                    required_permissions=list(
                        definition["required_permissions"]
                    ),
                    side_effect=str(definition["side_effect"]),
                    timeout_seconds=int(definition.get("timeout_seconds", 5)),
                    max_attempts=int(definition.get("max_attempts", 1)),
                    provider_config=dict(definition["provider_config"]),
                )
                session.add(version)
                await session.flush()
                skill.active_version_id = version.id

        await session.commit()


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
