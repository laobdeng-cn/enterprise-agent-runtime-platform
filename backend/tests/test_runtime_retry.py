from app.runtime.retry import RuntimeRetryPolicy


def test_runtime_retry_policy_is_bounded() -> None:
    policy = RuntimeRetryPolicy(
        max_attempts=3,
        base_delay_seconds=0.5,
        max_delay_seconds=1.0,
    )

    assert policy.should_retry(attempt=1, retryable=True)
    assert policy.should_retry(attempt=2, retryable=True)
    assert not policy.should_retry(attempt=3, retryable=True)
    assert not policy.should_retry(attempt=1, retryable=False)

    assert policy.delay_seconds(attempt=1) == 0.5
    assert policy.delay_seconds(attempt=2) == 1.0
    assert policy.delay_seconds(attempt=3) == 1.0
