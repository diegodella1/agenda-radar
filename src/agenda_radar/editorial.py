import time

from .models import ConfigVersion, State
from .schemas import EditorialConfig
from .security import audit


def active_config(session) -> tuple[int, EditorialConfig]:
    state = session.get(State, "active_config")
    version = session.get(ConfigVersion, state.value["id"]) if state else None
    if not version:
        return 0, EditorialConfig()
    return version.id, EditorialConfig.model_validate(version.payload)


def initialize_config(session):
    if not session.get(State, "active_config"):
        version = ConfigVersion(payload=EditorialConfig().model_dump())
        session.add(version)
        session.flush()
        session.add(State(key="active_config", value={"id": version.id}))


def publish_config(session, config: EditorialConfig, actor: int, reason: str):
    previous, _ = active_config(session)
    version = ConfigVersion(payload=config.model_dump(), created_by=actor, reason=reason)
    session.add(version)
    session.flush()
    session.merge(State(key="active_config", value={"id": version.id}))
    audit(
        session, actor, "publish", "config", version.id, {"version": previous}, {"reason": reason}
    )
    return version.id


def heartbeat(session):
    session.merge(State(key="worker_heartbeat", value={"at": time.time()}))
