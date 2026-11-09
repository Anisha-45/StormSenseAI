"""Password hashing, JWT tokens and role-based permissions."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
from datetime import datetime, timedelta, timezone

import jwt

try:  # bcrypt is the production choice; scrypt (standard library) is a safe fallback where it is not installed
    import bcrypt
except Exception:  # pragma: no cover
    bcrypt = None

from . import config

ROLES = ("administrator", "coordinator", "responder", "researcher", "citizen")
# What each role may do. Citizens never get administrative or operational permissions.
PERMISSIONS = {
    "administrator": {"analytics", "run_experiments", "upload_data", "report_incident", "review_incidents", "view_all_incidents",
                      "manage_resources", "view_resources", "manage_tasks", "view_tasks", "admin", "generate_reports"},
    "coordinator": {"analytics", "report_incident", "review_incidents", "view_all_incidents", "manage_resources", "view_resources",
                    "manage_tasks", "view_tasks", "generate_reports"},
    "responder": {"analytics", "report_incident", "view_all_incidents", "view_resources", "view_tasks", "update_own_tasks"},
    "researcher": {"analytics", "run_experiments", "upload_data", "generate_reports"},
    "citizen": {"report_incident"},
}
SELF_REGISTER_ROLES = ("citizen", "researcher")  # elevated roles are granted by an administrator only
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    if bcrypt is not None:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        if hashed.startswith("scrypt$"):
            _, salt_b64, dk_b64 = hashed.split("$")
            dk = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), n=2 ** 14, r=8, p=1, dklen=32)
            return hmac.compare_digest(dk, base64.b64decode(dk_b64))
        if bcrypt is None:
            return False
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def validate_password(password: str) -> list[str]:
    problems = []
    if len(password) < 8:
        problems.append("Password must be at least 8 characters.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        problems.append("Password must contain letters and digits.")
    return problems


def create_token(user_id: int, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": exp}, config.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())
