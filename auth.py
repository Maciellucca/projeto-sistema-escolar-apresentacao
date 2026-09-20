import hashlib
import secrets
from functools import wraps

from flask import session, redirect, url_for, request, abort
from werkzeug.security import generate_password_hash, check_password_hash

from models import get_db


# ---------------------------------------------------------------- staff ----
def hash_password(raw):
    return generate_password_hash(raw)


def verify_password(raw, hashed):
    return check_password_hash(hashed, raw)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("staff.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def roles_required(*papeis):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("staff.login", next=request.path))
            if session.get("papel") not in papeis:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def current_user():
    if not session.get("user_id"):
        return None
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    return row


# ------------------------------------------------------------- guardian ----
def new_guardian_token():
    """Gera um token para o responsavel (mostrado 1 vez ao staff) e o hash
    que fica salvo no banco. Nunca guardamos o token em texto puro."""
    token = secrets.token_urlsafe(24)
    return token, hash_token(token)


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def guardian_student_from_token(token):
    if not token:
        return None
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM students WHERE guardian_token_hash = ?", (hash_token(token),)
        ).fetchone()
    return row
