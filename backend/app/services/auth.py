"""Registration, login and token-to-user resolution, independent of the web framework so it can be unit tested."""
from __future__ import annotations

import jwt

from ..core import security as S
from ..db import database as db


class AuthError(Exception):
    """Authentication failed (HTTP 401)."""


class Forbidden(Exception):
    """Authenticated but not allowed (HTTP 403)."""


def register(con, email: str, name: str, password: str, role: str = "citizen") -> dict:
    email = (email or "").strip().lower()
    if not S.EMAIL_RE.match(email):
        raise ValueError("Invalid email address.")
    name = (name or "").strip()
    if not 2 <= len(name) <= 100:
        raise ValueError("Name must be 2-100 characters.")
    problems = S.validate_password(password or "")
    if problems:
        raise ValueError(" ".join(problems))
    if role not in S.SELF_REGISTER_ROLES:
        raise Forbidden(f"Self-registration is limited to roles: {', '.join(S.SELF_REGISTER_ROLES)}.")
    if db.one(con, "SELECT id FROM users WHERE email=?", (email,)):
        raise ValueError("An account with this email already exists.")
    cur = con.execute("INSERT INTO users(email,name,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                      (email, name, S.hash_password(password), role, db.now()))
    return public_user(db.one(con, "SELECT * FROM users WHERE id=?", (cur.lastrowid,)))


def create_privileged_user(con, admin: dict, email: str, name: str, password: str, role: str) -> dict:
    if not S.has_permission(admin["role"], "admin"):
        raise Forbidden("Administrator permission required.")
    if role not in S.ROLES:
        raise ValueError(f"role must be one of {S.ROLES}")
    user = register(con, email, name, password, role="citizen")
    con.execute("UPDATE users SET role=? WHERE id=?", (role, user["id"]))
    db.audit(con, admin["id"], "user_create", f"user:{user['id']}", f"role={role}")
    return {**user, "role": role}


def login(con, email: str, password: str) -> dict:
    u = db.one(con, "SELECT * FROM users WHERE email=?", ((email or "").strip().lower(),))
    # identical error for unknown email and wrong password: do not reveal which accounts exist
    if not u or not u["active"] or not S.verify_password(password or "", u["password_hash"]):
        raise AuthError("Invalid email or password.")
    return {"access_token": S.create_token(u["id"], u["role"]), "token_type": "bearer", "user": public_user(u)}


def user_from_token(con, token: str) -> dict:
    try:
        claims = S.decode_token(token)
    except jwt.PyJWTError as e:
        raise AuthError("Invalid or expired token.") from e
    u = db.one(con, "SELECT * FROM users WHERE id=?", (int(claims["sub"]),))
    if not u or not u["active"]:
        raise AuthError("Account not found or disabled.")
    return public_user(u)  # role comes from the database, never from the token


def require(user: dict, permission: str) -> None:
    if not S.has_permission(user["role"], permission):
        raise Forbidden(f"Your role ({user['role']}) does not have permission: {permission}.")


def public_user(u: dict) -> dict:
    return {"id": u["id"], "email": u["email"], "name": u["name"], "role": u["role"], "created_at": u["created_at"]}
