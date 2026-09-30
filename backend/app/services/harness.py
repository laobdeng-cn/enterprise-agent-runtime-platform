from app.agents.harness.providers.deepseek import DeepSeekProvider
from app.agents.harness.registry import ModelProviderRegistry
from app.agents.harness.runner import AgentHarness
from app.core.config import settings
from app.services.memory import memory_capabilities
from app.services.sandbox import sandbox_execution_service
from app.services.workspaces import workspace_capabilities
from app.skills.executor import SkillExecutor
from app.skills.local_handlers import LOCAL_SKILL_HANDLERS
from app.skills.providers.local import LocalSkillAdapter
from app.skills.providers.memory import MemorySkillAdapter
from app.skills.providers.sandbox import SandboxSkillAdapter
from app.skills.providers.workspace import WorkspaceSkillAdapter
from app.skills.registry import SkillProviderRegistry


def build_skill_executor() -> SkillExecutor:
    skill_providers = SkillProviderRegistry()
    skill_providers.register(
        "local",
        LocalSkillAdapter(LOCAL_SKILL_HANDLERS),
    )
    skill_providers.register(
        "workspace",
        WorkspaceSkillAdapter(workspace_capabilities),
    )
    skill_providers.register(
        "sandbox",
        SandboxSkillAdapter(sandbox_execution_service),
    )
    skill_providers.register(
        "memory",
        MemorySkillAdapter(memory_capabilities),
    )
    return SkillExecutor(skill_providers)


def build_agent_harness(executor: SkillExecutor) -> AgentHarness:
    model_providers = ModelProviderRegistry()
    model_providers.register(
        "deepseek",
        lambda: DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout_seconds=settings.deepseek_timeout_seconds,
        ),
    )
    return AgentHarness(
        providers=model_providers,
        skill_executor=executor,
    )


skill_executor = build_skill_executor()
agent_harness = build_agent_harness(skill_executor)
