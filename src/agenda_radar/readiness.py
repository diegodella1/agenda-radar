"""Configuration diagnostics without exposing credentials."""

import time

from sqlalchemy import select

from .editorial import active_config
from .models import Secret, Source, State, User


def report(db, settings):
    with db.session() as session:
        _, config = active_config(session)
        sources = list(session.scalars(select(Source).where(Source.enabled.is_(True))))
        providers = set(session.scalars(select(Secret.name)))
        pulse = session.get(State, "worker_heartbeat")
        checks = {
            "administrator": bool(
                session.scalar(
                    select(User.id)
                    .where(User.role == "superadmin", User.enabled.is_(True))
                    .limit(1)
                )
            ),
            "worker": bool(pulse and time.time() - pulse.value["at"] < 120),
            "own_sources": any(s.scope == "own" for s in sources),
            "reference_sources": len({s.group_name for s in sources if s.scope == "reference"})
            >= 2,
            "https_configuration": settings.app_base_url.startswith("https://")
            and settings.cookie_secure,
            "run_enabled": config.run_enabled,
            "openai": "openai" in providers if config.ai_enabled else "disabled",
            "telegram": "telegram" in providers if config.telegram_enabled else "disabled",
        }
    return {
        "base_url": settings.app_base_url,
        "checks": checks,
        "ready_for_pilot": all(value is not False for value in checks.values()),
        "note": "No verifica DNS, TLS externo, acceso a proveedores ni calidad editorial.",
    }
