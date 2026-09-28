import asyncio
from time import perf_counter
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from app.agents.harness.contracts import ModelToolCall
from app.models.skill import SkillVersion
from app.skills.contracts import SkillErrorEnvelope, SkillExecutionResult
from app.skills.errors import (
    SkillError,
    SkillInputValidationError,
    SkillNotBoundError,
    SkillOutputValidationError,
    SkillPermissionDeniedError,
    SkillProviderConfigurationError,
    SkillProviderError,
    SkillTimeoutError,
)
from app.skills.registry import SkillProviderRegistry


class SkillExecutor:
    def __init__(self, providers: SkillProviderRegistry) -> None:
        self.providers = providers

    async def execute(
        self,
        call: ModelToolCall,
        *,
        bound_versions: list[SkillVersion],
        granted_permissions: set[str],
    ) -> SkillExecutionResult:
        started_at = perf_counter()
        by_name = {
            version.skill.name: version
            for version in bound_versions
            if version.skill.status == "active"
        }
        version = by_name.get(call.name)

        if version is None:
            return self._error_result(
                call=call,
                error=SkillNotBoundError(
                    f"Skill '{call.name}' is not bound to this AgentVersion"
                ),
                started_at=started_at,
            )

        missing_permissions = sorted(
            set(version.required_permissions) - granted_permissions
        )
        if missing_permissions:
            return self._error_result(
                call=call,
                error=SkillPermissionDeniedError(
                    "Missing Skill permissions: "
                    + ", ".join(missing_permissions)
                ),
                started_at=started_at,
            )

        try:
            self._validate_schema(version.input_schema, call.arguments)
        except SkillInputValidationError as exc:
            return self._error_result(
                call=call,
                error=exc,
                started_at=started_at,
            )

        max_attempts = max(1, version.max_attempts)
        last_error: SkillError | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                adapter = self.providers.resolve(version.skill.provider_type)
                async with asyncio.timeout(version.timeout_seconds):
                    output = await adapter.execute(version, call.arguments)
                self._validate_output(version.output_schema, output)
                return SkillExecutionResult(
                    call_id=call.id,
                    skill_name=call.name,
                    ok=True,
                    output=output,
                    attempts=attempt,
                    duration_ms=(perf_counter() - started_at) * 1000,
                    metadata={
                        "skill_version_id": str(version.id),
                        "skill_version": version.version,
                        "side_effect": version.side_effect,
                    },
                )
            except TimeoutError:
                last_error = SkillTimeoutError(
                    f"Skill '{call.name}' exceeded "
                    f"{version.timeout_seconds}s timeout"
                )
            except SkillOutputValidationError as exc:
                last_error = exc
            except SkillProviderConfigurationError as exc:
                last_error = exc
            except SkillProviderError as exc:
                last_error = exc
            except Exception as exc:
                last_error = SkillProviderError(
                    f"Skill provider failed with {exc.__class__.__name__}"
                )

            if not last_error.retryable or attempt >= max_attempts:
                return self._error_result(
                    call=call,
                    error=last_error,
                    started_at=started_at,
                    attempts=attempt,
                )

        assert last_error is not None
        return self._error_result(
            call=call,
            error=last_error,
            started_at=started_at,
            attempts=max_attempts,
        )

    @staticmethod
    def _validate_schema(schema: dict[str, Any], value: Any) -> None:
        try:
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(value)
        except (SchemaError, ValidationError) as exc:
            raise SkillInputValidationError(str(exc.message)) from exc

    @staticmethod
    def _validate_output(schema: dict[str, Any], value: Any) -> None:
        try:
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(value)
        except (SchemaError, ValidationError) as exc:
            raise SkillOutputValidationError(str(exc.message)) from exc

    @staticmethod
    def _error_result(
        *,
        call: ModelToolCall,
        error: SkillError,
        started_at: float,
        attempts: int = 1,
    ) -> SkillExecutionResult:
        return SkillExecutionResult(
            call_id=call.id,
            skill_name=call.name,
            ok=False,
            error=SkillErrorEnvelope(
                code=error.code,
                retryable=error.retryable,
                message=str(error),
            ),
            attempts=attempts,
            duration_ms=(perf_counter() - started_at) * 1000,
        )
