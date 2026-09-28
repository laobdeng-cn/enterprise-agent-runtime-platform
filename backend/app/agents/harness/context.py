from app.agents.harness.contracts import ContextPackage


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
    ) -> ContextPackage:
        return ContextPackage(
            system_instructions=system_instructions,
            user_input=user_input,
            additional_context=list(additional_context or []),
        )
