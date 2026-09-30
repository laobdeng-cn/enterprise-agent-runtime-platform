from app.agents.harness.contracts import ContextPackage, MemoryContextItem


class ContextBuilder:
    """Phase 3 context assembler.

    Phase 9 replaces this basic assembly with token-budgeted context engineering.
    """

    def build(
        self,
        *,
        system_instructions: str,
        user_input: str,
        additional_context: list[str] | None = None,
        relevant_memory: list[MemoryContextItem] | None = None,
    ) -> ContextPackage:
        return ContextPackage(
            system_instructions=system_instructions,
            user_input=user_input,
            additional_context=list(additional_context or []),
            relevant_memory=list(relevant_memory or []),
        )
