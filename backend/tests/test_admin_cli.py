from __future__ import annotations

from app.cli import admin as admin_cli
from app.models.user import User


class _Service:
    def __init__(self):
        self.calls = []

    def bootstrap(self, **kwargs):
        self.calls.append(("bootstrap", kwargs))
        return User(
            username=kwargs["username"],
            password="stored-hash",
            role="admin",
        ), True

    def promote(self, username):
        self.calls.append(("promote", {"username": username}))
        return User(username=username, password="stored-hash", role="admin")

    def reset_password(self, username, password):
        self.calls.append(("reset", {"username": username, "password": password}))
        return User(username=username, password="stored-hash", role="admin")


def test_parser_does_not_accept_plaintext_password_argument():
    parser = admin_cli.build_parser()

    actions = parser._subparsers._group_actions[0].choices["bootstrap"]._actions

    assert all(action.dest != "password" for action in actions)


def test_bootstrap_uses_secure_environment_input_without_echo(monkeypatch, capsys):
    service = _Service()
    monkeypatch.setenv("MIEMIE_ADMIN_PASSWORD", "secret-from-env")
    monkeypatch.setattr(admin_cli, "build_admin_bootstrap_service", lambda: service)

    exit_code = admin_cli.main(["bootstrap", "--username", "owner"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert service.calls == [
        (
            "bootstrap",
            {
                "username": "owner",
                "display_name": None,
                "password": "secret-from-env",
            },
        )
    ]
    assert "secret-from-env" not in captured.out
    assert "secret-from-env" not in captured.err


def test_interactive_password_confirmation_mismatch_fails_without_service_call(
    monkeypatch,
    capsys,
):
    service = _Service()
    monkeypatch.delenv("MIEMIE_ADMIN_PASSWORD", raising=False)
    answers = iter(["first-secret", "different-secret"])
    monkeypatch.setattr(admin_cli.getpass, "getpass", lambda prompt: next(answers))
    monkeypatch.setattr(admin_cli, "build_admin_bootstrap_service", lambda: service)

    exit_code = admin_cli.main(["bootstrap", "--username", "owner"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert service.calls == []
    assert "password_confirmation_mismatch" in captured.err
    assert "first-secret" not in captured.err
