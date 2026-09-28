from app.skills.errors import SkillProviderConfigurationError
from app.skills.providers.base import SkillProviderAdapter


class SkillProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, SkillProviderAdapter] = {}

    def register(self, provider_type: str, adapter: SkillProviderAdapter) -> None:
        normalized = provider_type.strip().lower()
        if not normalized:
            raise ValueError("Skill provider type cannot be empty")
        self._providers[normalized] = adapter

    def resolve(self, provider_type: str) -> SkillProviderAdapter:
        normalized = provider_type.strip().lower()
        adapter = self._providers.get(normalized)
        if adapter is None:
            raise SkillProviderConfigurationError(
                f"Skill provider '{normalized}' is not registered"
            )
        return adapter

    @property
    def provider_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))
