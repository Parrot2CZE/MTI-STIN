"""
Autentizace uživatelů.

Session-based přihlášení s bcrypt hashy uloženými v config.yml.
Session je nastavena jako permanentní (přežije zavření prohlížeče),
životnost řídí PERMANENT_SESSION_LIFETIME v config.py.
"""

from __future__ import annotations

import bcrypt
from flask import session
from app.app_config_loader import get_users


def verify_password(username: str, password: str) -> bool:
    """
    Ověří kombinaci jméno/heslo proti config.yml.
    bcrypt.checkpw porovnává v konstantním čase, takže nehrozí timing attack.
    """
    for user in get_users():
        if user["username"] == username:
            stored = user["password_hash"].encode("utf-8")
            return bcrypt.checkpw(password.encode("utf-8"), stored)
    # Neznámý uživatel — vracíme False stejně jako špatné heslo
    return False


def login_user(username: str) -> None:
    """
    Zapíše username do session.
    session.permanent = True znamená, že session přežije zavření prohlížeče —
    životnost je omezena PERMANENT_SESSION_LIFETIME (výchozí 30 dní).
    """
    session["user"] = username
    session.permanent = True


def logout_user() -> None:
    session.pop("user", None)
    session.permanent = False


def current_user() -> str | None:
    return session.get("user")


def is_logged_in() -> bool:
    return "user" in session
