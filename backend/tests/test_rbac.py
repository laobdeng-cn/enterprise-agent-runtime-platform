import uuid

from app.models.identity import Permission, Role, User
from app.services.auth import permission_codes


def test_permission_codes_merge_multiple_roles() -> None:
    read_permission = Permission(
        id=uuid.uuid4(),
        code="agent:read",
        description="Read agents",
    )
    run_permission = Permission(
        id=uuid.uuid4(),
        code="run:create",
        description="Create runs",
    )

    reader_role = Role(
        id=uuid.uuid4(),
        name="reader",
        description="Reader",
        permissions=[read_permission],
    )
    runner_role = Role(
        id=uuid.uuid4(),
        name="runner",
        description="Runner",
        permissions=[run_permission],
    )

    user = User(
        id=uuid.uuid4(),
        username="test",
        password_hash="unused",
        roles=[reader_role, runner_role],
    )

    assert permission_codes(user) == {"agent:read", "run:create"}
