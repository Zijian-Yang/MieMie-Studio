"""Host-only administrator bootstrap and recovery CLI."""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from app.services.admin_bootstrap import (
    AdminAlreadyConfigured,
    BootstrapUserNotFound,
    ExistingUserRequiresPromotion,
    build_admin_bootstrap_service,
)


def _password_from_secure_input(*, confirmation: bool) -> str:
    password = os.getenv("MIEMIE_ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Administrator password: ")
        if confirmation and password != getpass.getpass("Confirm password: "):
            raise ValueError("password_confirmation_mismatch")
    if len(password) < 8:
        raise ValueError("password_too_short")
    return password


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="miemie-admin")
    commands = parser.add_subparsers(dest="command", required=True)

    bootstrap = commands.add_parser("bootstrap", help="create the first administrator")
    bootstrap.add_argument("--username", required=True)
    bootstrap.add_argument("--display-name")

    promote = commands.add_parser("promote", help="promote an existing user explicitly")
    promote.add_argument("username")

    reset = commands.add_parser("reset-password", help="reset an administrator credential")
    reset.add_argument("username")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = build_admin_bootstrap_service()
    try:
        if args.command == "bootstrap":
            user, created = service.bootstrap(
                username=args.username,
                display_name=args.display_name,
                password=_password_from_secure_input(confirmation=True),
            )
            state = "created" if created else "already-configured"
            print(f"administrator {state}: {user.username}")
        elif args.command == "promote":
            user = service.promote(args.username)
            print(f"administrator promoted: {user.username}")
        else:
            user = service.reset_password(
                args.username,
                _password_from_secure_input(confirmation=True),
            )
            print(f"administrator credential reset: {user.username}")
        return 0
    except ExistingUserRequiresPromotion:
        print("existing user requires explicit promote command", file=sys.stderr)
    except AdminAlreadyConfigured:
        print("another administrator is already configured", file=sys.stderr)
    except BootstrapUserNotFound:
        print("target user was not found", file=sys.stderr)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
