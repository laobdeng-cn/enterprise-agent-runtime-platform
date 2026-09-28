class HarnessError(RuntimeError):
    """Base class for normalized Agent Harness failures."""


class ProviderError(HarnessError):
    code = "provider_error"
    retryable = False

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ProviderConfigurationError(ProviderError):
    code = "provider_configuration"


class ProviderAuthenticationError(ProviderError):
    code = "provider_authentication"


class ProviderRateLimitError(ProviderError):
    code = "provider_rate_limit"
    retryable = True


class ProviderTimeoutError(ProviderError):
    code = "provider_timeout"
    retryable = True


class ProviderUpstreamError(ProviderError):
    code = "provider_upstream"
    retryable = True


class ProviderResponseError(ProviderError):
    code = "provider_response"
