from mcp.server.transport_security import TransportSecuritySettings


def internal_transport_security(hostname: str) -> TransportSecuritySettings:
    return TransportSecuritySettings(
        allowed_hosts=[
            hostname,
            f"{hostname}:*",
            "localhost",
            "localhost:*",
            "127.0.0.1",
            "127.0.0.1:*",
        ],
        allowed_origins=[],
    )
