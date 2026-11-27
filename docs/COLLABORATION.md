# Agents, Slack and private AI

One installation serves one newsroom. English is the default; Spanish is selectable in the
web interface, agents and Slack destinations. New integrations remain disabled until configured.
The public demo remains fictional and never connects to Slack or a model.

## Start with a preview

Open **Agents & collaboration** in the workspace navigation. Editors can follow, claim,
dismiss, mute or complete stories and record useful/noise feedback. Dismiss/noise actions
require a reason. A story can only be claimed by one editor; reassignment is not automated.
Existing web and Telegram follow/dismiss decisions also update the follow-up record.

Media administrators can create:

- **Vigilance:** stories with alerts produced by the existing editorial rules.
- **Briefing:** a daily selection ordered by editorial priority, at the configured local hour.
- **Follow-up:** new evidence for stories a person explicitly decided to follow.

Choose topics, source IDs, time window, language, destination and optional AI profile.
An empty filter means all eligible sources/topics. Preview is deterministic and sends nothing;
“Preview with AI” queues a bounded model run when AI is enabled. Missing evidence produces
an empty preview, not invented stories. Without AI, agents still produce evidence-based cards.
Agents inspect up to 200 recent active stories and return at most ten per run. This is a bounded
pilot implementation, not exhaustive discovery across arbitrarily large archives.

## Source policies and model routing

Every source defaults to **internal** unless explicitly set to **external** in the new screen.
External means its evidence may be included in Slack and cloud-model requests. If a document
has multiple observed sources, all must permit external use. Documents with no observed source
are internal. Notes and decision reasons are not part of Slack/model evidence.

Policy is checked before generating a Slack message and again before delivery. Revoking any
supporting source cancels the entire pending generated message. This cannot recall content already
sent to Slack or a provider. Legacy Telegram administrative notifications retain their existing
behavior; this new sharing policy is specifically enforced for Slack and model evidence.

Superadmins create AI profiles for **OpenAI**, **Claude/Anthropic**, or an internal
**OpenAI-compatible Chat Completions** endpoint such as Ollama/vLLM. Configure model, endpoint,
limits and credentials; save disabled, test, then enable. Tests use synthetic content and may
consume provider quota. A test validates the configured endpoint/model's structured-output path,
not factual quality. Use editorial evaluation before enabling scheduled analysis.

Assign profiles to questions and extraction. Other assistant purposes inherit the questions
profile unless explicitly mapped through the API. Each agent can select its own profile.
Once task routing is configured, an unassigned task stays disabled; it never falls through to
the old cloud credential. Enable AI globally in Editorial criteria, and extraction separately.
Legacy OpenAI configuration, when present during initialization, is imported as a disabled
profile with its credential retained in the encrypted vault. New connections require testing.

For internal endpoints:

1. Set `AI_INTERNAL_HOSTS` to the exact comma-separated hostnames/IPs permitted by the operator.
2. Ensure the collaboration container can route to that host on the enterprise network.
3. Use an internal API base URL including its `/v1` path. Redirects are not followed; DNS
   addresses are validated and the selected address is pinned for the request.
4. For a private certificate authority, place its PEM in `secrets/ai-certificates/` and set the
   profile CA path to `/app/certificates/<file>.pem`. TLS verification remains enabled.

The deployment does not install or run a local model, expose an internal model publicly, or
build a VPN. Internal hosts are independently authorized; news scraping still rejects private
addresses. Cloud providers use fixed HTTPS endpoints. Private failures never switch to cloud.

Request/token limits apply to internal models too. Blank price means unknown, not zero.
Set zero only when that is the intended accounting policy. Cloud profiles require prices;
daily/monthly dollar budgets include legacy and new calls. Failed/unknown calls retain a
conservative reservation. A profile allows one live request at a time.

## Slack installation

1. Create an internal Slack app using `deploy/slack-app-manifest.yaml`.
2. Install it into the newsroom workspace. Create an app-level token with `connections:write`
   for Socket Mode. Keep this separate from the bot token.
3. In Agenda Radar, enter workspace ID, bot token and app token. Authorize channel IDs with
   `en` or `es`; invite the bot to those channels. Save disabled and test workspace access.
4. Enable the connection. Each editor clicks **Link my Slack account** and runs
   `/radar link <code>` in an authorized channel within ten minutes.
5. Preview an agent, then enable its schedule for one pilot channel.

Bot scopes: `chat:write`, `commands`, `app_mentions:read`. No workspace-history scopes.
Use `/radar agenda`, `/radar gaps` (or `brechas`), `/radar briefing`, `/radar help`, or mention
the bot with a question. Agenda/briefing commands show up to five eligible evidence items;
scheduled briefing agents provide configurable selections and optional synthesis.

Cards offer evidence links and Follow, Dismiss, Mute 2h and I’ll review. Dismiss opens a reason
modal. Updates for an event reuse its channel thread. User permission and channel authorization
are checked before processing and before delivering query answers. A linked identity does not
grant permissions beyond its Agenda Radar account. Everyone in an authorized channel can see
messages posted there; use channels whose membership is appropriate for the approved sources.

Socket envelopes are acknowledged before model work. Queries are durable jobs; the receiver
does not execute models. The worker reconnects when configuration changes; the SDK handles
socket reconnects. Restricted/rejected interactions are visible as `slack_last_error` in state.
The web status screen exposes runs, delivery states and the process heartbeat.

Default scheduled-message cap is six per channel per hour. Quiet hours default to 23:00–07:00;
equal start/end disables quiet hours. Explicit query replies bypass quiet hours, while retaining
source and permission checks. Rate-limit/server rejections are retried, respecting Retry-After.
An ambiguous network send or interrupted sending process is marked failed for review rather
than blindly posting a duplicate. Slack message deduplication is best-effort, not exactly-once.

## Processes, rollout and rollback

- `web`: UI and authenticated APIs.
- `worker`: ingestion, scoring, backups and existing Telegram polling.
- `collaboration-worker`: model jobs, agent schedules, Slack receipt and delivery in independent loops.
- `tunnel`: HTTPS ingress.

`scripts/activate-production.sh` now creates a SQLite backup, applies additive migration 0002,
then starts/replaces all services. Do not run old and new main workers concurrently. Migration
0002 adds tables; it does not replace existing users, sources, decisions or credentials.
For rollback, disable Slack/agents, stop the collaboration service, and use the previous image
for web/worker. The extra tables can remain; do not downgrade a live database to discard history.
Retain the backup and master key together according to the existing backup procedure.

## APIs and validation

Superadmin: `/api/v1/admin/ai-profiles`, `/{id}/test`, `/ai-routing`, `/slack`, `/slack/test`.
Media admin: `/api/v1/admin/agents`, `/{id}/preview`, `/{id}/preview-ai`,
`/sources/{id}/data-policy`, `/collaboration-status`.
Editor: `/api/v1/slack/pair`, `/api/v1/editorial/followups`, `/followups/{event_id}`.
Writes retain the existing session, CSRF and role requirements. Secret fields are write-only.
Model tests and AI previews return a job ID for the existing jobs API.

Automated checks cover private-source filtering, revoked deliveries, identity/channel permissions,
deduplication, provider failures without fallback, quotas, structured transport, unsupported citations,
URLs/numbers, bilingual instructions, migrations and independent queues. Browser checks cover
configuration/preview and EN/ES at 1440/390/320 px. Tests use fixtures and simulated transports.
They do not establish factual model accuracy, successful access to your Slack workspace, or reachability
of your enterprise server. No real workspace credentials or enterprise endpoint were supplied.

For pilot acceptance, have editors label a representative corpus (including corrections,
duplicate reporting and missing sources), then compare usefulness/noise, decisions and completed
follow-ups. This human evaluation is a deployment activity; synthetic tests are not a substitute.

Primary API references:
- https://docs.slack.dev/apis/events-api/using-socket-mode/
- https://docs.slack.dev/interactivity/handling-user-interaction
- https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx
