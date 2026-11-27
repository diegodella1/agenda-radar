import hashlib
import secrets
import time
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import select

from .models import Audit, Secret, User

ROLES = {"reader": 0, "analyst": 1, "editor": 2, "media_admin": 3, "superadmin": 4}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password: str) -> str:
    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

    if not 12 <= len(password) <= 256:
        raise ValueError("Contraseña de 12 a 256 caracteres")
    return Argon2id(
        salt=secrets.token_bytes(16), length=32, iterations=2, lanes=1, memory_cost=19456
    ).derive_phc_encoded(password.encode())


def verify_password(password: str, stored: str) -> bool:
    from cryptography.exceptions import InvalidKey
    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

    try:
        Argon2id.verify_phc_encoded(password.encode(), stored)
        return True
    except (InvalidKey, ValueError):
        return False


def create_user(session, email, password, role="superadmin"):
    if role not in ROLES:
        raise ValueError("Rol inválido")
    if session.scalar(select(User.id).where(User.email == email.lower())):
        raise ValueError("Usuario existente")
    user = User(email=email.lower(), password_hash=hash_password(password), role=role)
    session.add(user)
    session.flush()
    return user


def audit(session, actor, action, kind, object_id="", before=None, after=None):
    session.add(
        Audit(
            actor_id=actor,
            action=action,
            object_kind=kind,
            object_id=str(object_id),
            before=before or {},
            after=after or {},
        )
    )


class Vault:
    def __init__(self, directory: Path):
        self.path = directory / "master.key"

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.path.exists():
            import os

            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as file:
                file.write(Fernet.generate_key())

    def cipher(self):
        return Fernet(self.path.read_bytes())

    def set(self, session, name, value):
        if name not in ("openai", "telegram", "x", "slack_bot", "slack_app") and not (name.startswith("ai:") and name[3:].isdigit()):
            raise ValueError("Proveedor inválido")
        session.merge(Secret(name=name, encrypted=self.cipher().encrypt(value.encode()).decode()))

    def get(self, session, name):
        secret = session.get(Secret, name)
        return self.cipher().decrypt(secret.encrypted.encode()).decode() if secret else None


def pairing_code(session, user_id):
    from .models import TelegramLink

    code = secrets.token_urlsafe(24)
    link = session.get(TelegramLink, user_id) or TelegramLink(user_id=user_id)
    link.code_hash = digest(code)
    link.expires_at = time.time() + 600
    session.add(link)
    return code
