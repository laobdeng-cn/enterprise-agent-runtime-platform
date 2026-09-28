class SkillError(RuntimeError):
    code = "SKILL_ERROR"
    retryable = False


class SkillNotBoundError(SkillError):
    code = "SKILL_NOT_BOUND"


class SkillPermissionDeniedError(SkillError):
    code = "SKILL_PERMISSION_DENIED"


class SkillInputValidationError(SkillError):
    code = "SKILL_INPUT_VALIDATION"


class SkillOutputValidationError(SkillError):
    code = "SKILL_OUTPUT_VALIDATION"


class SkillProviderConfigurationError(SkillError):
    code = "SKILL_PROVIDER_CONFIGURATION"


class SkillProviderError(SkillError):
    code = "SKILL_PROVIDER_ERROR"


class SkillRetryableProviderError(SkillProviderError):
    code = "SKILL_PROVIDER_RETRYABLE"
    retryable = True


class SkillTimeoutError(SkillError):
    code = "SKILL_TIMEOUT"
    retryable = True


class SkillExecutionContextError(SkillError):
    code = "SKILL_EXECUTION_CONTEXT"
