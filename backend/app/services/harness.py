from app.agents.harness.providers.deepseek import DeepSeekProvider
from app.agents.harness.registry import ModelProviderRegistry
from app.agents.harness.runner import AgentHarness
from app.core.config import settings


def build_agent_harness() -> AgentHarness:
    providers = ModelProviderRegistry()
    providers.register(
        "deepseek",
        lambda: DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout_seconds=settings.deepseek_timeout_seconds,
        ),
    )
    return AgentHarness(providers=providers)


agent_harness = build_agent_harness()
