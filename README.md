<div align="center">

# 📡 Agenda Radar

**Know what matters. See what is missing. Decide what to cover.**

Self-hosted media monitoring and editorial coordination for newsrooms.<br>
Compare coverage, trace every signal to its sources, and turn editorial decisions into follow-up.

[🧭 Explore the demo](https://aradar.diegodella.ar/demo/) · [🌐 Product website](https://aradar.diegodella.ar/home) · [🚀 Getting started](#getting-started) · [📚 Documentation](#documentation)

![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)

![Self-hosted](https://img.shields.io/badge/Deployment-Self--hosted-334155?style=flat-square)
![English and Spanish](https://img.shields.io/badge/Languages-EN%20%2F%20ES-6366F1?style=flat-square)
[![Try the demo](https://img.shields.io/badge/Demo-Try%20it%20live-0D9488?style=flat-square)](https://aradar.diegodella.ar/demo/)
[![CI workflow](https://img.shields.io/badge/GitHub_Actions-CI%20workflow-2088FF?style=flat-square&logo=githubactions&logoColor=white)](https://github.com/diegodella1/agenda-radar/actions/workflows/ci.yml)

</div>

---

## 📰 From scattered headlines to editorial decisions

Agenda Radar brings your newsroom’s coverage and reference sources into one workspace. It groups related reporting into stories, compares editorial priorities, highlights potential coverage gaps, and keeps the evidence behind each decision accessible.

Built for **one newsroom per installation**, it runs on your own infrastructure with a web interface, background workers, and optional Slack, Telegram, and AI integrations. Core monitoring and deterministic agent previews work without an AI provider.

> **Try it first:** the [public demo](https://aradar.diegodella.ar/demo/) needs no account. Its stories, publishers, and metrics are fictional; edits stay in your browser. It does not connect to live sources, messaging services, or AI providers.

## ✨ What you can do

| Capability | What it brings to your newsroom |
| --- | --- |
| 📥 **Monitor sources** | Collect RSS/Atom feeds, selected web pages, Google News, and manual entries; inspect source health and import sources by CSV or optional starter packs. |
| 🧩 **Group related reporting** | Deduplicate documents and cluster stories with deterministic text and entity signals, then correct groupings through human review, split, and merge. |
| ⚖️ **Compare coverage** | Compare your own agenda with reference outlets across 1-hour, 6-hour, 24-hour, 72-hour, and 7-day windows. Inspect supporting publications before acting. |
| 🎯 **Set editorial priorities** | Configure topics, source weights, rules, and prompts. Preview changes, publish versioned settings, and restore earlier criteria as a new version. |
| 📈 **Track emerging signals** | Review coverage-gap, emerging-story, priority, agenda-shift, and impact alerts alongside Google Trends and optional X signals. |
| 🤝 **Coordinate decisions** | Follow, dismiss, claim, mute, or complete stories; record reasons and useful/noise feedback; retain decision history and ownership. |
| 🔎 **Ask evidence-based questions** | Query stored evidence and export Markdown. Optional AI adds synthesis and extraction with output validation, budgets, and explicit limitations. |
| 🌐 **Work in two languages** | Use English by default or select Spanish across the public site, workspace, and demo. User-authored editorial content is not automatically translated. |

A missing article is not automatically a coverage gap. Comparisons account for source health and the declared completeness of manual coverage. Scoring and clustering remain reviewable heuristics, not guarantees of editorial importance or factual accuracy.

## 🤝 Editorial agents and collaboration

Three agent types support recurring newsroom work:

- 🔭 **Vigilance** surfaces stories flagged by editorial alert rules.
- 🗞️ **Briefing** prepares a daily selection ordered by editorial priority.
- 📌 **Follow-up** tracks new evidence for stories an editor chose to follow.

Configure topics, sources, time windows, language, destination, and an optional AI profile. Preview before enabling a schedule. Delivery records support the **web workspace, Slack, and Telegram**, subject to each integration’s configuration and permissions.

Slack uses Socket Mode, linked newsroom identities, authorized channels, threaded updates, commands, and decision buttons. Telegram provides private-chat linking, agenda queries, alerts, and role-checked decisions.

AI profiles support **OpenAI**, **Claude / Anthropic**, and authorized internal **OpenAI-compatible Chat Completions endpoints**, such as Ollama or vLLM. Profiles can be assigned to individual tasks and agents. Internal-provider failures do not silently fall back to a cloud provider.

Sources default to an internal data policy. External sharing requires explicit permission; model requests and collaboration deliveries apply evidence policies. Connections start disabled and require configuration and testing. See the [collaboration guide](docs/COLLABORATION.md) for permissions, routing, limits, and rollout details.

<a id="getting-started"></a>

## 🚀 Getting started

### Local development

Requires **Python 3.12+** and **SQLite with FTS5**. Run these commands from the repository root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
.venv/bin/python -m agenda_radar.cli init
.venv/bin/python -m agenda_radar.cli create-admin --email editor@example.com
.venv/bin/python -m agenda_radar.cli web
```

The administrator password is requested interactively. Open **http://127.0.0.1:8765**.

Start ingestion and maintenance in a second terminal:

```sh
.venv/bin/python -m agenda_radar.cli worker
```

For agent schedules, model jobs, and collaboration delivery, start a third process:

```sh
.venv/bin/python -m agenda_radar.cli collaboration-worker
```

The example environment enables collaboration processing, while individual external integrations remain disabled. `COOKIE_SECURE=false` is only for HTTP development on loopback. For shared access, configure HTTPS, set `COOKIE_SECURE=true`, and set `APP_BASE_URL` to your deployment URL.

### First newsroom workflow

1. **Add sources.** Register reference outlets and your own publication, including editorial group and usage basis. Test a source or import a starter pack before collecting at scale.
2. **Collect evidence.** Run the worker and inspect source health and capture history.
3. **Compare agendas.** Open the radar, choose a time window, and inspect each story’s supporting publications.
4. **Tune priorities.** Preview and publish your newsroom’s topics, weights, and rules.
5. **Make decisions.** Follow or dismiss a story, claim responsibility, record coverage, or correct its grouping.
6. **Enable integrations when ready.** Configure provider credentials, evidence-sharing policies, budgets, and destinations; test a real operation before enabling scheduled delivery.

If your own coverage is entered manually, explicitly maintain `manual_coverage_complete_until` in UTC. An incomplete manual list is not evidence that your newsroom has missed a story.

### Docker

The basic Compose file runs the web application and ingestion worker:

```sh
docker compose build
docker compose run --rm web python -m agenda_radar.cli init
docker compose run --rm web python -m agenda_radar.cli create-admin --email editor@example.com
docker compose up -d
```

Copy and configure `.env.example` first, including your URL and cookie settings. The published port binds to loopback, and persistent data uses named volumes. Run migrations before starting services.

The [production Compose file](compose.production.yaml) additionally defines collaboration processing and HTTPS ingress. It contains installation-specific image tags, paths, and tunnel settings: adapt it to your infrastructure before use. See [operations](docs/OPERATIONS.md) and [collaboration deployment](docs/COLLABORATION.md#processes-rollout-and-rollback).

## 🏗️ Architecture

| Layer | Implementation |
| --- | --- |
| Web and API | FastAPI, Uvicorn, Pydantic, server-rendered Jinja2 templates |
| Interface | Native JavaScript and Fetch, CSS, accessible SVG charts, locally served assets |
| Persistence | SQLite with FTS5, SQLAlchemy, Alembic migrations |
| Main worker | Source ingestion, scoring, alerts, maintenance, backups, and Telegram polling |
| Collaboration worker | Agent schedules, queued model work, Slack reception, and delivery processing |
| Access and secrets | Role-based permissions, session authentication, CSRF protection, Argon2id passwords, Fernet-encrypted secrets |
| Deployment | Python processes or Docker; no Node.js runtime required in production |

```text
src/agenda_radar/   Application, workers, connectors, templates, and static assets
scripts/           Installation, operations, benchmarks, and browser checks
tests/             Automated tests and isolated fixtures
docs/              Setup guides, design notes, operations, and specifications
deploy/            Deployment assets and Slack app manifest
```

Public health endpoints are `/health/live` and `/health/ready`. Detailed diagnostics and the OpenAPI document at `/api/v1/openapi.json` require authentication. API writes require a session, `X-Requested-With: AgendaRadar`, and an `X-CSRF-Token`; queued operations return a job ID.

## 🧪 Validation and operating limits

Run the Python checks:

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests scripts
.venv/bin/python -m mypy src/agenda_radar
```

CI also checks JavaScript syntax, tests job polling, and builds a wheel. Browser smoke scripts live in `scripts/`; they require a separate Node.js / Playwright test environment. Use isolated test data for browser tests and benchmarks.

- **Editorial control stays human.** Agenda Radar does not automatically publish articles or social posts.
- **External integrations are optional.** X requires appropriate API access; messaging and model providers require your own credentials, permissions, and quota.
- **Signals have limits.** Unresolved aggregator links do not count as independent publishers. Trend volume retains its own units, and agent selections are bounded rather than exhaustive.
- **Tests are not pilot acceptance.** Fixtures and simulated transports do not establish model accuracy, real-workspace connectivity, or editorial usefulness on your corpus.
- **Recovery includes secrets.** Keep database backups and the encryption master key available for recovery, with appropriate access controls. Test restoration to a separate destination.

<a id="documentation"></a>

## 📚 Documentation

Some operational guides and historical specifications are currently in Spanish.

| Guide | Contents |
| --- | --- |
| [Setup and operation](docs/CONFIGURAR_Y_PROBAR.md) | Account setup, configuration, and first operational checks |
| [Agents, Slack, and private AI](docs/COLLABORATION.md) | Agent previews, source policies, provider routing, and integration setup |
| [Editorial criteria](docs/CRITERIA_EDITOR.md) | Weights, rules, previews, and versioned configuration |
| [Operations and recovery](docs/OPERATIONS.md) | Maintenance, backups, diagnostics, and restoration |
| [Public demo](docs/DEMO.md) | Demo behavior and operational context |
| [Public website](docs/PUBLIC_SITE.md) | Public pages and product presentation |
| [Delivery and validation history](STATUS.md) | Dated implementation evidence, deployment notes, and outstanding validation |
| [Original specifications](docs/specification/00_LEEME.md) | Product requirements and architectural decisions |

Historical notes describe earlier implementations; use the current code and the latest dated entries when assessing behavior.
