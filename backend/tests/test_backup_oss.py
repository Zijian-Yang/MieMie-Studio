from __future__ import annotations

from pathlib import Path

import pytest

from app.models.platform_operations import PlatformOperationsSettings
from app.services.backup_oss import BackupOSSClient, BackupOSSError


def _settings(**changes):
    values = {
        "backup_oss_enabled": True,
        "backup_oss_endpoint": "https://oss-cn-test.aliyuncs.com",
        "backup_oss_bucket_name": "platform-backups",
        "backup_oss_prefix": "miemie/backups",
        "backup_oss_access_key_id": "LTAI-platform-key",
        "backup_oss_access_key_secret": "platform-secret",
    }
    values.update(changes)
    return PlatformOperationsSettings(**values)


class _Response:
    def __init__(self, etag='"etag-value"'):
        self.etag = etag


class _Bucket:
    def __init__(self, *, fail_put=False, fail_head=False, fail_delete=False):
        self.fail_put = fail_put
        self.fail_head = fail_head
        self.fail_delete = fail_delete
        self.calls = []

    def put_object(self, key, content):
        self.calls.append(("put_object", key, content))
        if self.fail_put:
            raise RuntimeError("private endpoint and credential details")
        return _Response()

    def head_object(self, key):
        self.calls.append(("head_object", key))
        if self.fail_head:
            raise RuntimeError("private response body")
        return _Response()

    def delete_object(self, key):
        self.calls.append(("delete_object", key))
        if self.fail_delete:
            raise RuntimeError("private cleanup response")
        return _Response()

    def put_object_from_file(self, key, path):
        self.calls.append(("put_object_from_file", key, path))
        if self.fail_put:
            raise RuntimeError("private upload response")
        return _Response('"uploaded-etag"')


class _Factory:
    def __init__(self, bucket):
        self.bucket = bucket
        self.calls = []

    def __call__(self, access_key_id, access_key_secret, endpoint, bucket_name):
        self.calls.append((access_key_id, access_key_secret, endpoint, bucket_name))
        return self.bucket


def test_connection_test_uses_dedicated_settings_and_always_cleans_object():
    bucket = _Bucket()
    factory = _Factory(bucket)
    client = BackupOSSClient(bucket_factory=factory, id_factory=lambda: "check-123")

    result = client.test(_settings())

    assert result.succeeded is True
    assert result.etag == "etag-value"
    assert result.object_key == "miemie/backups/_checks/check-123.txt"
    assert factory.calls == [
        (
            "LTAI-platform-key",
            "platform-secret",
            "https://oss-cn-test.aliyuncs.com",
            "platform-backups",
        )
    ]
    assert [call[0] for call in bucket.calls] == [
        "put_object",
        "head_object",
        "delete_object",
    ]


def test_test_object_is_deleted_when_verification_fails():
    bucket = _Bucket(fail_head=True)
    client = BackupOSSClient(
        bucket_factory=_Factory(bucket), id_factory=lambda: "check-failed"
    )

    with pytest.raises(BackupOSSError) as exc:
        client.test(_settings())

    assert exc.value.category == "oss_test_verification_failed"
    assert bucket.calls[-1][0] == "delete_object"
    assert "private" not in str(exc.value)


def test_cleanup_failure_is_reported_without_leaking_details():
    bucket = _Bucket(fail_delete=True)
    client = BackupOSSClient(
        bucket_factory=_Factory(bucket), id_factory=lambda: "check-cleanup"
    )

    with pytest.raises(BackupOSSError) as exc:
        client.test(_settings())

    assert exc.value.category == "oss_test_cleanup_failed"
    assert str(exc.value) == "oss_test_cleanup_failed"


def test_upload_uses_deterministic_object_key_and_returns_etag(tmp_path):
    path = tmp_path / "miemie-postgres-20260812-030405-run.dump"
    path.write_bytes(b"PGDMPbackup")
    bucket = _Bucket()
    client = BackupOSSClient(bucket_factory=_Factory(bucket))
    key = client.object_key(path, _settings())

    result = client.upload(path, key, _settings())

    assert key == "miemie/backups/miemie-postgres-20260812-030405-run.dump"
    assert result.succeeded is True
    assert result.object_key == key
    assert result.etag == "uploaded-etag"
    assert result.size_bytes == len(b"PGDMPbackup")
    assert bucket.calls == [("put_object_from_file", key, str(path))]


@pytest.mark.parametrize(
    "key",
    ("../outside.dump", "/absolute.dump", "miemie/backups/../../outside.dump"),
)
def test_upload_rejects_unsafe_object_keys(tmp_path, key):
    path = tmp_path / "backup.dump"
    path.write_bytes(b"PGDMPbackup")
    client = BackupOSSClient(bucket_factory=_Factory(_Bucket()))

    with pytest.raises(BackupOSSError) as exc:
        client.upload(path, key, _settings())
    assert exc.value.category == "oss_object_key_invalid"


def test_upload_failure_is_secret_free(tmp_path):
    path = tmp_path / "backup.dump"
    path.write_bytes(b"PGDMPbackup")
    client = BackupOSSClient(bucket_factory=_Factory(_Bucket(fail_put=True)))

    with pytest.raises(BackupOSSError) as exc:
        client.upload(path, "miemie/backups/backup.dump", _settings())

    serialized = str(exc.value)
    assert serialized == "oss_upload_failed"
    for forbidden in ("LTAI-platform-key", "platform-secret", "aliyuncs.com"):
        assert forbidden not in serialized


def test_incomplete_configuration_and_missing_file_are_rejected(tmp_path):
    client = BackupOSSClient(bucket_factory=_Factory(_Bucket()))
    incomplete = _settings(
        backup_oss_enabled=False,
        backup_oss_access_key_id=None,
        backup_oss_access_key_secret=None,
    )
    with pytest.raises(BackupOSSError, match="oss_configuration_incomplete"):
        client.test(incomplete)
    with pytest.raises(BackupOSSError, match="oss_backup_file_invalid"):
        client.upload(
            tmp_path / "missing.dump",
            "miemie/backups/missing.dump",
            _settings(),
        )
