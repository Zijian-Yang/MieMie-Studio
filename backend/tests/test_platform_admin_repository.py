from __future__ import annotations

from app.models.user import User
from app.repositories.platform_admin import (
    AdminAuditEvent,
    LastActiveAdmin,
    PostgresAdminUserRepository,
)
from app.repositories.user_config import user_to_row


class _Result:
    def __init__(self, value=None):
        self.value = value

    def mappings(self):
        return self

    def first(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value

    def scalar_one(self):
        return self.value


class _Connection:
    def __init__(self, results):
        self.results = list(results)
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)
        if self.results:
            return _Result(self.results.pop(0))
        return _Result()


class _Context:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, traceback):
        return False


class _Engine:
    def __init__(self, results):
        self.connection = _Connection(results)

    def begin(self):
        return _Context(self.connection)


def _user_row(user_id="admin-1", *, role="admin"):
    return user_to_row(
        User(
            id=user_id,
            username=user_id,
            password="stored-hash",
            role=role,
            status="active",
        )
    )


def _event(target_id="admin-1"):
    return AdminAuditEvent(
        actor_user_id="admin-2",
        action="admin.user.update",
        target_type="user",
        target_id=target_id,
        request_id="req-1",
        changes={"role": "member"},
    )


def test_security_update_locks_target_and_active_admin_set_before_writes():
    engine = _Engine(["platform", _user_row(), ["admin-1", "admin-2"]])
    repository = PostgresAdminUserRepository(engine)

    updated = repository.update_user("admin-1", {"role": "member"}, _event())

    sql = [str(statement) for statement in engine.connection.statements]
    assert updated.role == "member"
    assert "platform_settings" in sql[0]
    assert "FOR UPDATE" in sql[0]
    assert "FOR UPDATE" in sql[1]
    assert "users.role =" in sql[2]
    assert "FOR UPDATE" in sql[2]
    assert sql[3].startswith("UPDATE users SET")
    assert sql[4].startswith("INSERT INTO admin_audit_logs")


def test_last_active_admin_conflict_happens_before_update_or_audit():
    engine = _Engine(["platform", _user_row(), ["admin-1"]])
    repository = PostgresAdminUserRepository(engine)

    try:
        repository.update_user("admin-1", {"status": "disabled"}, _event())
    except LastActiveAdmin:
        pass
    else:
        raise AssertionError("last active administrator must be protected")

    sql = [str(statement) for statement in engine.connection.statements]
    assert len(sql) == 3
    assert all("FOR UPDATE" in statement for statement in sql)


def test_soft_delete_only_marks_identity_row_and_preserves_business_data():
    engine = _Engine(["platform", _user_row("member-1", role="member")])
    repository = PostgresAdminUserRepository(engine)

    deleted = repository.soft_delete_user("member-1", _event("member-1"))

    sql = [str(statement) for statement in engine.connection.statements]
    assert deleted.id == "member-1"
    assert "platform_settings" in sql[0]
    assert "FOR UPDATE" in sql[1]
    assert sql[2].startswith("UPDATE users SET")
    assert "deleted_at" in sql[2]
    assert "projects" not in " ".join(sql)
    assert "user_configs" not in " ".join(sql)
    assert sql[3].startswith("INSERT INTO admin_audit_logs")
