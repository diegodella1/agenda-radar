"""Single-use first administrator enrollment, enabled only by a local operator."""

import os
import secrets
import time

from sqlalchemy import select, text

from .models import State, User
from .security import audit, create_user, digest


def prepare(db, directory):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / "setup-code"
    code = secrets.token_urlsafe(32)
    with db.session() as session:
        session.execute(text("BEGIN IMMEDIATE"))
        if session.scalar(select(User.id).limit(1)):
            raise ValueError("Ya existen usuarios; usar create-admin desde consola")
        session.merge(
            State(
                key="bootstrap",
                value={
                    "hash": digest(code),
                    "expires_at": time.time() + 86400,
                },
            )
        )
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as file:
            file.write(code + "\n")
    return path


def enroll(db, code, email, password):
    with db.session() as session:
        session.execute(text("BEGIN IMMEDIATE"))
        state = session.get(State, "bootstrap")
        if (
            session.scalar(select(User.id).limit(1))
            or not state
            or state.value["expires_at"] < time.time()
            or not secrets.compare_digest(state.value["hash"], digest(code))
        ):
            raise ValueError("Código inválido, vencido o instalación ya completada")
        if "@" not in email or len(email) > 254:
            raise ValueError("Correo inválido")
        user = create_user(session, email.strip(), password)
        audit(session, user.id, "bootstrap", "user", user.id)
        session.delete(state)
