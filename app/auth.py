from __future__ import annotations

import bcrypt
from flask import session
from app.app_config_loader import get_users


def verify_password(username: str, password: str) -> bool:
    """Ověří uživatelské jméno a heslo proti config.yml."""
    for user in get_users():
        if user["username"] == username:
            stored = user["password_hash"].encode("utf-8")
            return bcrypt.checkpw(password.encode("utf-8"), stored)
    return False


def login_user(username: str) -> None:
    session["user"] = username
    session.permanent = False


def logout_user() -> None:
    session.pop("user", None)


def current_user() -> str | None:
    return session.get("user")


def is_logged_in() -> bool:
    return "user" in session
