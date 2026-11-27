import time
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from .editorial import active_config
from .models import Alert, Notification, State, TelegramLink, User

RULE_LABELS = {
    "editorial_gap": "Brecha editorial",
    "emerging_event": "Acontecimiento emergente",
    "priority_without_coverage": "Prioridad sin cobertura",
    "agenda_shift": "Cambio de agenda",
    "high_impact_update": "Actualización de alto impacto",
}


def evaluate_alerts(session, comparison):
    version, config = active_config(session)
    now = comparison["as_of"]
    key = "alert_baseline:" + comparison["window"]
    baseline = session.get(State, key)
    old = baseline.value if baseline else {}
    same_config = old.get("version") == version
    healthy = (
        comparison["source_health"]["own"] == "healthy"
        and comparison["reference_healthy_ratio"] >= 0.8
    )
    previous_rows = old.get("rows", {}) if same_config and old.get("healthy") else {}
    count = 0
    checkpoints = {}
    for row in comparison["rows"]:
        prior = previous_rows.get(str(row["event_id"]))
        checkpoints[str(row["event_id"])] = (
            dict(prior)
            if prior and now - prior.get("checkpoint_at", now) < 86400
            else {
                "share": row["reference_share"],
                "documents": [d["id"] for d in row["documents"]],
                "checkpoint_at": now,
            }
        )
        checkpoints[str(row["event_id"])]["qualified"] = bool(
            healthy
            and row["independent_source_count"] >= config.minimum_independent_sources
            and row["confidence"] >= config.minimum_confidence
        )
    for row in comparison["rows"]:
        if (
            not healthy
            or row["reference_share"] is None
            or row["independent_source_count"] < config.minimum_independent_sources
            or row["confidence"] < config.minimum_confidence
            or row["excluded"]
            or row["requires_review"]
        ):
            continue
        previous_row = previous_rows.get(str(row["event_id"]))
        new_ids = set(d["id"] for d in row["documents"]) - set(
            previous_row.get("documents", []) if previous_row else []
        )
        shift = (
            row["reference_share"] - previous_row["share"]
            if previous_row and previous_row["share"] is not None
            else None
        )
        candidates = []
        if previous_row and len(new_ids) >= config.high_impact_new_documents:
            candidates.append(("high_impact_update", len(new_ids)))
        if shift is not None and abs(shift) >= config.agenda_shift_pp:
            candidates.append(("agenda_shift", row["reference_share"]))
        if (
            same_config
            and old.get("healthy")
            and (not previous_row or not previous_row.get("qualified"))
            and row["velocity"] >= config.emerging_velocity
        ):
            candidates.append(("emerging_event", row["independent_source_count"]))
        if row["gap_pp"] is not None and row["gap_pp"] >= config.minimum_gap_pp:
            candidates.append(("editorial_gap", row["gap_pp"]))
        if not row["own_covered"] and row["priority"] >= config.priority_threshold:
            candidates.append(("priority_without_coverage", row["priority"] * 100))
        # One notification per event per evaluation; more specific rules take precedence.
        candidates = [
            (rule, metric) for rule, metric in candidates if rule in config.enabled_alert_rules
        ]
        if not candidates:
            continue
        rule, metric = candidates[0]
        previous = session.scalar(
            select(Alert)
            .where(Alert.event_id == row["event_id"], Alert.rule == rule)
            .order_by(Alert.at.desc())
            .limit(1)
        )
        insufficient_change = (
            previous
            and rule in ("editorial_gap", "priority_without_coverage", "agenda_shift")
            and abs(
                metric - previous.payload.get("trigger_metric", previous.payload.get("gap_pp") or 0)
            )
            < config.rearm_change_pp
        )
        if previous and (now - previous.at < config.cooldown_minutes * 60 or insufficient_change):
            continue
        payload = {
            **row,
            "rule_label": RULE_LABELS[rule],
            "trigger_metric": metric,
            "new_document_ids": sorted(new_ids),
            "change_pp": shift,
        }
        alert = Alert(
            event_id=row["event_id"],
            rule=rule,
            dedupe_key=f"{rule}:{row['event_id']}:{comparison['window']}:{version}:{int(now)}",
            at=now,
            payload=payload,
        )
        session.add(alert)
        session.flush()
        for link in session.scalars(
            select(TelegramLink)
            .join(User)
            .where(TelegramLink.chat_id.is_not(None), User.enabled.is_(True))
        ):
            session.add(
                Notification(alert_id=alert.id, user_id=link.user_id, expires_at=now + 6 * 3600)
            )
        count += 1
        checkpoints[str(row["event_id"])].update(
            share=row["reference_share"],
            documents=[d["id"] for d in row["documents"]],
            checkpoint_at=now,
        )
    session.merge(
        State(
            key=key,
            value={
                "version": version,
                "healthy": healthy,
                "at": now,
                "rows": checkpoints,
            },
        )
    )
    return count


def quiet(config, timezone, now=None):
    hour = datetime.fromtimestamp(now or time.time(), ZoneInfo(timezone)).hour
    start, end = config.quiet_start, config.quiet_end
    return (
        start <= hour < end
        if start < end
        else (hour >= start or hour < end)
        if start != end
        else False
    )


async def deliver_notifications(db, telegram, settings):
    with db.session() as session:
        _, config = active_config(session)
        if not config.telegram_enabled:
            return
        pending = list(
            session.scalars(
                select(Notification)
                .where(Notification.status == "pending", Notification.run_after <= time.time())
                .limit(20)
            )
        )
    for item in pending:
        with db.session() as session:
            notification = session.get(Notification, item.id)
            link, user = session.get(TelegramLink, item.user_id), session.get(User, item.user_id)
            if notification.expires_at < time.time():
                notification.status = "expired"
                continue
            if not link or not link.chat_id or not user or not user.enabled:
                notification.status = "cancelled"
                continue
            sent = session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user.id, Notification.sent_at >= time.time() - 43200)
            )
            health_history = session.get(State, f"health_sent:{user.id}")
            sent += len(
                [
                    at
                    for at in (health_history.value.get("timestamps", []) if health_history else [])
                    if at >= time.time() - 43200
                ]
            )
            if quiet(config, settings.app_timezone) or link.muted_until > time.time() or sent >= 6:
                notification.run_after = time.time() + 300
                continue
            alert = session.get(Alert, item.alert_id)
            row = alert.payload
            def _fmt(val, suffix=""):
                return f"{val:.1f}{suffix}" if val is not None else "sin datos"
            text = (
                f"{RULE_LABELS.get(alert.rule, alert.rule)} · {row['label']}\n"
                f"Referencia {_fmt(row.get('reference_share'), '%')} · Propia {_fmt(row.get('own_share'), '%')}\n"
                f"Brecha {_fmt(row.get('gap_pp'), ' pp')} · {row['independent_source_count']} grupos independientes\n"
                + "\n".join(d["url"] for d in row["documents"][:3])
                + f"\n{settings.app_base_url}/events/{alert.event_id}"
            )
            chat_id = link.chat_id
        try:
            await telegram.call(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": text[:4000],
                    "reply_markup": {
                        "inline_keyboard": [
                            [
                                {"text": "Seguir", "callback_data": f"follow:{alert.event_id}"},
                                {"text": "Descartar", "callback_data": f"dismiss:{alert.event_id}"},
                            ]
                        ]
                    },
                },
            )
            with db.session() as session:
                notification = session.get(Notification, item.id)
                notification.status, notification.sent_at = "sent", time.time()
        except Exception:
            with db.session() as session:
                notification = session.get(Notification, item.id)
                notification.attempt += 1
                notification.error_code = "telegram_delivery_failed"
                notification.run_after = time.time() + min(
                    3600, 30 * 2 ** min(notification.attempt, 6)
                )
