import time

import httpx
from sqlalchemy import select

from .editorial import active_config
from .jobs import enqueue
from .models import Decision, Event, Source, State, TelegramLink, User
from .scoring import compare
from .security import ROLES, audit, digest


class Telegram:
    def __init__(self, db, vault):
        self.db, self.vault = db, vault

    async def call(self, method, payload):
        with self.db.session() as session:
            token = self.vault.get(session, "telegram")
        if not token:
            raise ValueError("telegram_not_configured")
        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/{method}", json=payload
            )
            if response.status_code != 200:
                raise ValueError("telegram_api_error")
            body = response.json()
            if not body.get("ok"):
                raise ValueError("telegram_api_error")
            return body.get("result")

    async def poll(self):
        with self.db.session() as session:
            _, config = active_config(session)
            if not config.telegram_enabled or not self.vault.get(session, "telegram"):
                return
            cursor = session.get(State, "telegram_offset")
            offset = cursor.value["offset"] if cursor else 0
        updates = await self.call(
            "getUpdates",
            {"offset": offset, "timeout": 20, "allowed_updates": ["message", "callback_query"]},
        )
        for update in updates:
            await self.handle(update)
            with self.db.session() as session:
                session.merge(
                    State(key="telegram_offset", value={"offset": update["update_id"] + 1})
                )

    async def handle(self, update):
        message = update.get("message", update.get("callback_query", {}).get("message", {}))
        chat = message.get("chat", {})
        if chat.get("type") != "private":
            return
        chat_id = chat.get("id")
        body = message.get("text", "").strip()
        callback_id = update.get("callback_query", {}).get("id")
        with self.db.session() as session:
            handled_key = f"telegram_handled:{update['update_id']}"
            if session.get(State, handled_key):
                return
            if body.startswith("/start "):
                link = session.scalar(
                    select(TelegramLink).where(
                        TelegramLink.code_hash == digest(body.split(" ", 1)[1]),
                        TelegramLink.expires_at > time.time(),
                    )
                )
                if link and session.get(User, link.user_id).enabled:
                    existing = session.scalar(
                        select(TelegramLink).where(TelegramLink.chat_id == chat_id)
                    )
                    if not existing or existing.user_id == link.user_id:
                        link.chat_id, link.code_hash, link.expires_at = chat_id, None, 0
                        audit(session, link.user_id, "pair", "telegram")
                        response = "Telegram vinculado. Usá /ayuda."
                    else:
                        response = "Este chat ya está vinculado."
                else:
                    response = "Código inválido o vencido."
            else:
                link = session.scalar(select(TelegramLink).where(TelegramLink.chat_id == chat_id))
                user = session.get(User, link.user_id) if link else None
                if not user or not user.enabled:
                    return
                callback = update.get("callback_query", {}).get("data", "")
                if callback:
                    if ROLES[user.role] < ROLES["editor"]:
                        response = "Tu rol no permite registrar decisiones."
                    else:
                        action, _, identifier = callback.partition(":")
                        event = (
                            session.get(Event, int(identifier)) if identifier.isdigit() else None
                        )
                        if action not in ("follow", "dismiss") or not event:
                            return
                        session.merge(State(key=handled_key, value={"at": time.time()}))
                        session.add(
                            Decision(
                                event_id=event.id, user_id=user.id, action=action, reason="Telegram"
                            )
                        )
                        audit(session, user.id, action, "event", event.id)
                        from .collaboration_models import EditorialFollowup
                        follow = session.get(EditorialFollowup, event.id) or EditorialFollowup(event_id=event.id)
                        follow.status = 'following' if action == 'follow' else 'dismissed'
                        follow.updated_at = time.time()
                        session.add(follow)
                        response = "Decisión registrada."
                elif body.startswith("/silenciar"):
                    argument = body.split(maxsplit=1)[1] if " " in body else "2h"
                    try:
                        hours = min(168, max(1, int(argument.rstrip("h"))))
                    except ValueError:
                        hours = 2
                    link.muted_until = time.time() + hours * 3600
                    response = f"Notificaciones silenciadas por {hours} horas."
                elif body.startswith("/fuentes"):
                    response = (
                        "\n".join(f"{s.name}: {s.status}" for s in session.scalars(select(Source)))
                        or "Sin fuentes."
                    )
                elif body.startswith(("/agenda", "/brechas")):
                    requested_window = body.split(maxsplit=1)[1] if " " in body else "24h"
                    if requested_window not in ("1h", "6h", "24h", "72h", "7d"):
                        requested_window = "24h"
                    rows = compare(session, requested_window)["rows"]
                    if body.startswith("/brechas"):
                        rows = [r for r in rows if r["gap_pp"] is not None and r["gap_pp"] > 0]
                    response = (
                        "\n\n".join(
                            r["label"] + "\n" + "\n".join(d["url"] for d in r["documents"][:2])
                            for r in rows[:5]
                        )
                        or "Sin datos suficientes."
                    )
                elif body in ("/ayuda", "/start"):
                    response = "/agenda · /brechas · /tema consulta · /fuentes · /silenciar 2h. Consultas basadas en el monitoreo guardado."
                else:
                    if ROLES[user.role] < ROLES["editor"]:
                        response = "Consultas de análisis disponibles para editores."
                    else:
                        # Enqueue after transaction closes to avoid a second writer holding a lock.
                        query = body.removeprefix("/tema ")[:2000]
                        response = None
                        user_id = user.id
        if response is None:
            enqueue(
                self.db,
                "telegram_query",
                {"query": query, "chat_id": chat_id},
                f"telegram:{update['update_id']}",
                user_id=user_id,
            )
            response = "Consulta recibida. Estoy revisando la evidencia."
        if callback_id:
            try:
                await self.call("answerCallbackQuery", {"callback_query_id": callback_id})
            except Exception:
                pass
        await self.call("sendMessage", {"chat_id": chat_id, "text": response[:4000]})
