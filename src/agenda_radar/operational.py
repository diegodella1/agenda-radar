"""Durable administrative incidents and retryable private notifications."""

import time

from sqlalchemy import func, select

from .alerts import quiet
from .editorial import active_config
from .models import Notification, Source, State, TelegramLink, User
from .scoring import source_healthy
from .security import audit


def evaluate_health(session, now=None):
    now = now or time.time()
    _, config = active_config(session)
    if not config.run_enabled or "source_health_failure" not in config.enabled_alert_rules:
        return
    for source in session.scalars(select(Source).where(Source.kind != "manual")):
        key = f"source_incident:{source.id}"
        state = session.get(State, key)
        failed = bool(
            source.error_code
            or (source.enabled and source.last_success and not source_healthy(source, now))
        )
        if failed and (not state or state.value["status"] == "resolved"):
            incident = {
                "source_id": source.id,
                "name": source.name,
                "error": source.error_code or "stale",
                "at": now,
                "status": "open",
            }
            session.merge(State(key=key, value=incident))
            audit(session, None, "source_health_failure", "source", source.id, after=incident)
            for link in session.scalars(
                select(TelegramLink)
                .join(User)
                .where(
                    TelegramLink.chat_id.is_not(None),
                    User.enabled.is_(True),
                    User.role.in_(["media_admin", "superadmin"]),
                )
            ):
                session.merge(
                    State(
                        key=f"health_outbox:{source.id}:{link.user_id}",
                        value={
                            **incident,
                            "user_id": link.user_id,
                            "status": "pending",
                            "attempt": 0,
                            "run_after": now,
                            "expires_at": now + 21600,
                        },
                    )
                )
        elif not failed and state and state.value["status"] == "open":
            state.value = {**state.value, "status": "resolved", "resolved_at": now}
            audit(session, None, "source_health_recovered", "source", source.id)


async def deliver_health(db, telegram, settings):
    with db.session() as session:
        _, config = active_config(session)
        if not config.telegram_enabled or "source_health_failure" not in config.enabled_alert_rules:
            return
        items = [
            (s.key, s.value)
            for s in session.scalars(select(State).where(State.key.like("health_outbox:%")))
            if s.value["status"] == "pending" and s.value["run_after"] <= time.time()
        ][:20]
    for key, value in items:
        with db.session() as session:
            user = session.get(User, value["user_id"])
            link = session.get(TelegramLink, value["user_id"])
            incident = session.get(State, f"source_incident:{value['source_id']}")
            state = session.get(State, key)
            if (
                not user
                or not user.enabled
                or user.role not in ("media_admin", "superadmin")
                or not link
                or not link.chat_id
                or time.time() > value["expires_at"]
                or not incident
                or incident.value["status"] == "resolved"
            ):
                state.value = {**value, "status": "cancelled"}
                continue
            if quiet(config, settings.app_timezone) or link.muted_until > time.time():
                state.value = {**value, "run_after": time.time() + 300}
                continue
            history = session.get(State, f"health_sent:{user.id}")
            recent = [
                at
                for at in (history.value.get("timestamps", []) if history else [])
                if at >= time.time() - 43200
            ]
            editorial_sent = session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user.id, Notification.sent_at >= time.time() - 43200)
            )
            if len(recent) + editorial_sent >= 6:
                state.value = {**value, "run_after": time.time() + 300}
                continue
            chat = link.chat_id
        try:
            await telegram.call(
                "sendMessage",
                {
                    "chat_id": chat,
                    "text": f"Fuente con problemas · {value['name']}\n{value['error']}\n"
                    f"{settings.app_base_url}/admin/sources",
                },
            )
            update = {"status": "sent", "sent_at": time.time()}
        except Exception:
            update = {
                "attempt": value["attempt"] + 1,
                "run_after": time.time() + min(3600, 30 * 2 ** min(value["attempt"], 6)),
            }
        with db.session() as session:
            state = session.get(State, key)
            # Do not overwrite a newer recovery/failure episode.
            if state.value["at"] == value["at"]:
                state.value = {**state.value, **update}
                if update.get("status") == "sent":
                    session.merge(
                        State(
                            key=f"health_sent:{value['user_id']}",
                            value={"timestamps": recent + [time.time()]},
                        )
                    )
