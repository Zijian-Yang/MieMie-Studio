from pathlib import Path

from app.services.user_service import UserService


def _service(tmp_path) -> UserService:
    service = UserService(data_dir=Path(tmp_path))
    service._redis_sessions = None
    return service


def test_disabled_user_cannot_login(tmp_path):
    service = _service(tmp_path)
    user = service.register("disabled-user", "pass1234")
    users = service._load_users()
    user.status = "disabled"
    service._save_user_record(users, user)

    assert service.login("disabled-user", "pass1234") is None


def test_disabled_user_token_is_rejected_and_revoked(tmp_path):
    service = _service(tmp_path)
    user = service.register("disabled-user", "pass1234")
    token, _ = service.login("disabled-user", "pass1234")
    users = service._load_users()
    user.status = "disabled"
    service._save_user_record(users, user)

    assert service.get_user_by_token(token) is None
    assert token not in service.sessions
