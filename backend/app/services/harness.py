from app.agents.harness.providers.deepseek import DeepSeekProvider
from app.agents.harness.registry import ModelProviderRegistry
from app.agents.harness.runner import AgentHarness
from app.core.config import settings
from app.skills.executor import SkillExecutor
from app.skills.local_handlers import LOCAL_SKILL_HANDLERS
from app.skills.providers.local import LocalSkillAdapter
from app.skills.registry import SkillProviderRegistry


def build_agent_harness() -> AgentHarness:
    model_providers = ModelProviderRegistry()
    model_providers.register(
        "deepseek",
        lambda: DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout_seconds=settings.deepseek_timeout_seconds,
        ),
    )

    skill_providers = SkillProviderRegistry()
    skill_providers.register(
        "local",
        LocalSkillAdapter(LOCAL_SKILL_HANDLERS),
    )

    return AgentHarness(
        providers=model_providers,
        skill_executor=SkillExecutor(skill_providers),
    )


agent_harness = build_agent_harness()
