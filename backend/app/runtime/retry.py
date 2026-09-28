from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeRetryPolicy:
    max_attempts: int
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 2.0

    def should_retry(self, *, attempt: int, retryable: bool) -> bool:
        return retryable and attempt < self.max_attempts

    def delay_seconds(self, *, attempt: int) -> float:
        exponent = max(attempt - 1, 0)
        return min(
            self.base_delay_seconds * (2**exponent),
            self.max_delay_seconds,
        )
