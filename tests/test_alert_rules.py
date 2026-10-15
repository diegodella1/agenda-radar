import asyncio
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from agenda_radar.alerts import evaluate_alerts
from agenda_radar.editorial import active_config, publish_config
from agenda_radar.models import Alert, Event, Source, State, TelegramLink, User
from agenda_radar.operational import deliver_health, evaluate_health


def comparison(event_id, now, **values):
    row = dict(
        event_id=event_id,
        label="Evidencia de prueba",
        topic="local",
        reference_share=30,
        own_share=0,
        gap_pp=30,
        own_covered=False,
        independent_source_count=3,
        confidence=0.9,
        excluded=False,
        requires_review=False,
        priority=0.9,
        velocity=2,
        documents=[{"id": 1, "url": "https://example.test/1"}],
    )
    row.update(values)
    return dict(
        as_of=now,
        window="24h",
        source_health={"own": "healthy"},
        reference_healthy_ratio=1,
        rows=[row],
    )


@pytest.mark.parametrize(
    "rule", ["agenda_shift", "high_impact_update", "emerging_event", "priority_without_coverage"]
)
def test_specialized_rules_and_dedup(app, rule):
    with app.state.db.session() as session:
        _, config = active_config(session)
        config.enabled_alert_rules = [rule]
        publish_config(session, config, 1, "Rule test")
        event = Event(label="Prueba", topic="local")
        session.add(event)
        session.flush()
        now = time.time()
        initial = comparison(event.id, now, priority=0)
        if rule == "emerging_event":
            initial["rows"] = []
        assert evaluate_alerts(session, initial) == 0
        current = comparison(event.id, now + 300)
        if rule == "agenda_shift":
            current["rows"][0]["reference_share"] = 60
        if rule == "high_impact_update":
            current["rows"][0]["documents"] += [
                {"id": n, "url": f"https://example.test/{n}"} for n in (2, 3, 4)
            ]
        assert evaluate_alerts(session, current) == 1
        session.flush()
        assert evaluate_alerts(session, current) == 0
        assert session.scalar(select(Alert)).rule == rule


def test_shift_suppressed_across_config_change_and_unhealthy_sources(app):
    with app.state.db.session() as session:
        _, config = active_config(session)
        config.enabled_alert_rules = ["agenda_shift"]
        publish_config(session, config, 1, "First config")
        event = Event(label="Prueba", topic="local")
        session.add(event)
        session.flush()
        now = time.time()
        evaluate_alerts(session, comparison(event.id, now))
        publish_config(session, config, 1, "Changed config")
        assert evaluate_alerts(session, comparison(event.id, now + 300, reference_share=70)) == 0
        bad = comparison(event.id, now + 600, reference_share=10)
        bad["reference_healthy_ratio"] = 0.5
        assert evaluate_alerts(session, bad) == 0


def test_health_incidents_only_notify_admin_and_resolve(app):
    db = app.state.db
    with db.session() as session:
        source = Source(
            name="Fixture",
            url="https://example.test/rss",
            group_name="Fixture",
            legal_basis="test fixture",
            status="degraded",
            error_code="http_503",
        )
        session.add(source)
        for user in session.scalars(select(User)):
            session.add(TelegramLink(user_id=user.id, chat_id=str(user.id)))
        session.flush()
        evaluate_health(session)
        session.flush()
        evaluate_health(session)
        outbox = list(session.scalars(select(State).where(State.key.like("health_outbox:%"))))
        assert len(outbox) == 1
        assert outbox[0].value["user_id"] == 1
        source.error_code = None
        source.status = "healthy"
        source.last_success = time.time()
        session.flush()
        evaluate_health(session)
        assert session.get(State, f"source_incident:{source.id}").value["status"] == "resolved"
        _, config = active_config(session)
        config.telegram_enabled = True
        config.quiet_start = config.quiet_end = 0
        publish_config(session, config, 1, "Health delivery")

    class NoSend:
        async def call(self, *args):
            raise AssertionError("Resolved incident must not be sent")

    asyncio.run(deliver_health(db, NoSend(), app.state.settings))
    with db.session() as session:
        assert (
            session.scalar(select(State).where(State.key.like("health_outbox:%"))).value["status"]
            == "cancelled"
        )


def test_password_change_revokes_sessions(client, app):
    assert (
        client.post(
            "/api/v1/auth/password",
            json={"current_password": "wrong", "new_password": "new-long-password"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/auth/password",
            json={"current_password": "a-long-test-password", "new_password": "new-long-password"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/events").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.test", "password": "new-long-password"},
        ).status_code
        == 200
    )


def test_backup_download_is_admin_only_and_blocks_other_files(client, app):
    path = app.state.settings.backup_dir / "agenda-1792077033000000000.db"
    app.state.db.backup(path)
    response = client.get("/api/v1/admin/backups/" + path.name)
    assert response.status_code == 200
    assert response.content.startswith(b"SQLite format 3")
    assert "attachment" in response.headers["content-disposition"]
    assert client.get("/api/v1/admin/backups/master.key").status_code == 404
    client.post("/api/v1/auth/logout", json={})
    assert client.get("/api/v1/admin/backups/" + path.name).status_code == 401


def test_prompt_suite_requires_all_fixed_cases(monkeypatch):
    from agenda_radar import prompt_evaluation

    def answer(*args, **kwargs):
        documents = kwargs["test_evidence"]
        case = next(c for c in prompt_evaluation.CASES if c["documents"] == documents)
        return {
            "mode": "ai",
            "citation_document_ids": case["expected_ids"],
            "answer": case["required"],
        }

    monkeypatch.setattr(prompt_evaluation, "answer_query", answer)
    prompt = SimpleNamespace(id=1, purpose="answer_telegram")
    assert prompt_evaluation.evaluate_prompt(None, None, prompt)["passed"]
    monkeypatch.setattr(
        prompt_evaluation,
        "answer_query",
        lambda *a, **kw: {"mode": "deterministic", "citation_document_ids": [], "answer": ""},
    )
    assert not prompt_evaluation.evaluate_prompt(None, None, prompt)["passed"]


def test_high_impact_accumulates_evidence_across_polls(app):
    with app.state.db.session() as session:
        _, config = active_config(session)
        config.enabled_alert_rules = ["high_impact_update"]
        publish_config(session, config, 1, "Accumulation")
        event = Event(label="Prueba", topic="local")
        session.add(event)
        session.flush()
        now = time.time()
        assert evaluate_alerts(session, comparison(event.id, now)) == 0
        for total in (2, 3, 4):
            result = comparison(
                event.id,
                now + 300 * total,
                documents=[
                    {"id": n, "url": f"https://example.test/{n}"} for n in range(1, total + 1)
                ],
            )
            assert evaluate_alerts(session, result) == (1 if total == 4 else 0)
