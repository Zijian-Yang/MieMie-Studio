from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.platform_operations import OperationRun
from app.repositories.base import RepositoryWriteError
from app.repositories.platform_admin import OperationRunRepository


class _Result:
    def __init__(self, value=None):
        self.value = value

    def mappings(self):
        return self

    def first(self):
        return self.value

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
        value = self.results.pop(0) if self.results else None
        return _Result(value)


class _Context:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, traceback):
        return False


class _Engine:
    def __init__(self, begin_results=(), connect_results=()):
        self.write = _Connection(begin_results)
        self.read = _Connection(connect_results)

    def begin(self):
        return _Context(self.write)

    def connect(self):
        return _Context(self.read)


class _ConflictConnection(_Connection):
    def execute(self, statement):
        self.statements.append(statement)
        raise IntegrityError("insert operation run", {}, RuntimeError("unique conflict"))


class _ConflictEngine(_Engine):
    def __init__(self, existing_row):
        super().__init__(connect_results=[existing_row])
        self.write = _ConflictConnection(())


def _run(status="queued"):
    now = datetime.now(timezone.utc)
    return OperationRun(
        id="run-1",
        operation_type="backup",
        status=status,
        trigger_source="manual",
        idempotency_key="backup:manual:run-1",
        created_at=now,
        updated_at=now,
    )


def test_claim_is_a_single_conditional_queued_to_running_update():
    running = _run(status="running").model_dump()
    engine = _Engine(begin_results=[running])

    claimed = OperationRunRepository(engine).claim("run-1")

    sql = str(engine.write.statements[0])
    assert claimed.status == "running"
    assert "operation_runs.status =" in sql
    assert "RETURNING" in sql


def test_create_returns_existing_run_after_idempotency_conflict():
    expected = _run()
    engine = _ConflictEngine(expected.model_dump())

    result, created = OperationRunRepository(engine).create(expected)

    assert created is False
    assert result.id == expected.id
    assert "operation_runs.idempotency_key =" in str(engine.read.statements[0])


def test_create_without_idempotency_key_does_not_hide_insert_failure():
    run = _run().model_copy(update={"idempotency_key": None})
    engine = _ConflictEngine(run.model_dump())

    with pytest.raises(RepositoryWriteError, match="Failed to create"):
        OperationRunRepository(engine).create(run)


def test_finish_only_accepts_running_and_filters_unknown_result_fields():
    succeeded = _run(status="succeeded").model_dump()
    succeeded.update(local_status="succeeded", oss_status="skipped")
    engine = _Engine(begin_results=[succeeded])

    result = OperationRunRepository(engine).finish(
        "run-1",
        succeeded=True,
        values={
            "local_status": "succeeded",
            "oss_status": "skipped",
            "dangerous_column": "must-not-be-written",
        },
    )

    sql = str(engine.write.statements[0])
    assert result.status == "succeeded"
    assert "operation_runs.status =" in sql
    assert "dangerous_column" not in sql


def test_finish_rejects_non_running_or_already_finished_run():
    engine = _Engine(begin_results=[None])

    with pytest.raises(RepositoryWriteError, match="not running"):
        OperationRunRepository(engine).finish("run-1", succeeded=False, values={})


def test_list_applies_filters_pagination_and_returns_typed_page():
    row = _run().model_dump()
    engine = _Engine(connect_results=[2, [row]])

    page = OperationRunRepository(engine).list(
        page=2,
        page_size=1,
        operation_type="backup",
        status="queued",
    )

    sql = [str(statement) for statement in engine.read.statements]
    assert page.total == 2
    assert page.items[0].id == "run-1"
    assert "operation_runs.operation_type =" in sql[0]
    assert "operation_runs.status =" in sql[0]
    assert "LIMIT" in sql[1] and "OFFSET" in sql[1]
