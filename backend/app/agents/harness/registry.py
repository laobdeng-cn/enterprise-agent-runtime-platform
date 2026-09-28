from collections.abc import Callable

from app.agents.harness.errors import ProviderConfigurationError
from app.agents.harness.providers.base import ModelProvider

ProviderFactory = Callable[[], ModelProvider]


class ModelProviderRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}

    def register(self, name: str, factory: ProviderFactory) -> None:
        normalized_name = name.strip().lower()
        if not normalized_name:
            raise ValueError("Provider name cannot be empty")
        self._factories[normalized_name] = factory

    def resolve(self, name: str) -> ModelProvider:
        normalized_name = name.strip().lower()
        factory = self._factories.get(normalized_name)
        if factory is None:
            raise ProviderConfigurationError(
                f"Model provider '{normalized_name}' is not registered"
            )
        return factory()

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))
