class SandboxError(RuntimeError):
    code = "SANDBOX_ERROR"


class SandboxUnavailableError(SandboxError):
    code = "SANDBOX_UNAVAILABLE"


class SandboxImageError(SandboxError):
    code = "SANDBOX_IMAGE_ERROR"


class SandboxExecutionInfrastructureError(SandboxError):
    code = "SANDBOX_EXECUTION_INFRASTRUCTURE"


class SandboxCodeTooLargeError(SandboxError):
    code = "SANDBOX_CODE_TOO_LARGE"


class SandboxOutputPolicyError(SandboxError):
    code = "SANDBOX_OUTPUT_POLICY"
