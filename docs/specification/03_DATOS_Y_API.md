# Modelo de datos y contrato API v1
**Objetivo:** habilitar trazabilidad de cada recomendación y mantener datos transportables.

## 1. Entidades persistentes (SQLite)
En lugar de guardar «una noticia con lista de URLs», preservar capas:

| Tabla | Claves y campos relevantes | Invariantes |
|---|---|---|
| `sources` | `id`, `name`, `kind`, `channel`, `url`, `scope`, `group_id`, `weight`, `status`, `poll_interval`, `last_success`, `legal_basis`, `auth_secret_ref` | fuente propia/reference/public; credenciales separadas |
| `source_groups` | `id`, `name`, `independence_group`, `category`, `weight` | 5 dominios de un grupo editorial no valen 5 opiniones independientes |
| `ingest_runs` | `id`, `source_id`, `started_at`, `ended_at`, `status`, `count`, `error_code`, `http_status` | diagnóstico y freshness |
| `documents` | `id`, `source_id`, `external_id`, `canonical_url`, `title`, `excerpt`, `author`, `published_at`, `observed_at`, `content_hash`, `raw_ref`, `license` | unique `(source_id, external_id)` donde exista; hash/URL dedupe |
| `document_versions` | `document_id`, `version`, `observed_at`, `hash`, `excerpt`, `changed_fields` | conservar correcciones |
| `events` | `id`, `canonical_label`, `summary`, `first_observed_at`, `started_at`, `topic_id`, `confidence`, `status` | acontecimiento ≠ post |
| `event_mentions` | `event_id`, `document_id`, `similarity`, `link_method`, `human_verified`, `observed_at` | N menciones de N fuentes; no descartar por repetición |
| `entities` | `id`, `type`, `canonical_name`, `aliases_json` | personas, instituciones, lugares |
| `document_entities` | `document_id`, `entity_id`, `role`, `evidence_span` | atribución a texto/URL |
| `topics` | `id`, `name`, `parent_id`, `keywords_json`, `status` | taxonomía personalizable |
| `editorial_rules` | `id`, `kind`, `version`, `expression_json`, `weight`, `status`, `author_id` | reglas versionadas, auditadas |
| `score_snapshots` | `event_id`, `window`, `as_of`, `config_version`, `observed`, `editorial`, `public`, `gap`, `confidence`, `components_json` | cálculo reproducible |
| `own_coverage` | `event_id`, `document_id`, `channel`, `status`, `published_at`, `manual_flag` | propio puede venir de RSS/CMS o registrarse manual |
| `trend_samples` | `provider`, `topic_text`, `geo`, `window`, `value`, `unit`, `captured_at`, `source_url`, `quality` | no mezclar unidades |
| `alerts` | `id`, `event_id`, `rule_id`, `severity`, `dedupe_key`, `status`, `explanation_json`, `created_at` | evita repetir 20 alertas |
| `notifications` | `alert_id`, `channel`, `recipient_ref`, `attempt`, `sent_at`, `delivery_status`, `error` | outbox resiliente |
| `decisions` | `event_id`, `user_id`, `action`, `reason`, `created_at`, `before_json`, `after_json` | aprueba/descarta/sigue/divide/fusiona |
| `prompts` | `id`, `purpose`, `version`, `template`, `model`, `parameters_json`, `status`, `created_by` | draft -> tested -> published -> retired |
| `api_usage` | `timestamp`, `provider`, `operation`, `model`, `input_tokens`, `output_tokens`, `estimated_usd`, `request_id` | presupuesto controlado |
| `users` | `id`, `email`, `password_hash`, `role`, `enabled`, `last_login` | RBAC backend |
| `audit_log` | `actor`, `action`, `object_kind`, `object_id`, `before_json`, `after_json`, `at` | append-only lógico |
| `jobs` | `id`, `kind`, `payload_json`, `status`, `attempt`, `run_after`, `lease_until`, `idempotency_key` | no broker extra |

Campos JSON viven en texto validado con Pydantic. Todas las fechas internas en UTC ISO8601; se muestran en zona de usuario. Usar índices `(source_id,published_at)`, `(event_id,observed_at)`, `(status,run_after)`, `(event_id,as_of)` y FTS5 sobre `documents(title,excerpt)` + etiquetas de eventos.

## 2. Contratos internos de ingesta
```json
{
  "source_id": "rss_lanacion_politica",
  "external_id": "guid:example:5432",
  "url": "https://example.com/nota",
  "title": "Título original",
  "excerpt": "Extracto permitido",
  "published_at": "2026-10-14T18:00:00Z",
  "observed_at": "2026-10-14T18:02:12Z",
  "channel": "web",
  "capture_method": "rss",
  "quality_flags": [],
  "provenance": {"feed_url":"https://example.com/rss"}
}
```

Acontecimientos exponen `document_ids`, `first_observed_by_us`, `last_seen_at`, `independent_source_count` y `score_breakdown`. La relación evento-documento siempre se puede reabrir; actualizaciones no destruyen evidencia.

## 3. API REST (esbozo contractual)
| Método | Endpoint | Rol | Resultado |
|---|---|---|---|
| GET | `/api/v1/events?window=24h&sort=gap` | reader+ | tarjetas + paginación |
| GET | `/api/v1/events/{id}` | reader+ | ficha, score, menciones |
| POST | `/api/v1/events/{id}/merge` | editor+ | fusionar con auditoría |
| POST | `/api/v1/events/{id}/split` | editor+ | dividir con auditoría |
| GET | `/api/v1/agendas/compare?window=24h` | reader+ | tres agendas + incertidumbre |
| GET | `/api/v1/trends?channel=x&window=6h` | reader+ | series + unidad y fecha |
| GET/POST/PATCH | `/api/v1/admin/sources` | media_admin+ | CRUD fuentes |
| GET/POST/PATCH | `/api/v1/admin/weights` | media_admin+ | pesos versionados |
| GET/POST/PATCH | `/api/v1/admin/rules` | media_admin+ | reglas por tipo |
| POST | `/api/v1/admin/config/preview` | media_admin+ | re-score sin publicar |
| POST | `/api/v1/admin/config/publish` | media_admin+ | versión activa |
| GET/POST | `/api/v1/admin/prompts` | superadmin | borradores/versiones |
| POST | `/api/v1/admin/prompts/{id}/test` | superadmin | eval + costo |
| POST | `/api/v1/admin/prompts/{id}/publish` | superadmin | activar versión |
| GET/POST | `/api/v1/admin/providers` | superadmin | estado; secretos nunca en respuesta |
| GET | `/api/v1/admin/health` | superadmin | conectores/jobs/DB/AI |
| POST | `/api/v1/editorial/decisions` | editor+ | log decisión |
| POST | `/api/v1/assistant/query` | editor+ | respuesta con evidencias |
| GET | `/api/v1/alerts` | reader+ | inbox alertas |
| POST | `/api/v1/alerts/{id}/ack` | editor+ | confirmación |

Seguridad: auth de cookie `HttpOnly`/`Secure`/`SameSite`, CSRF en mutaciones, RBAC evaluado servidor, validación de payloads, rate limits y paginación en listados. Endpoints de configuración no admiten cambios desde Telegram (solo decisiones editoriales no destructivas permitidas y con identidad vinculada).

## 4. Versionado y consistencia
Usar `schema_version`, `config_version`, `algorithm_version` en snapshots. Al cambiar pesos, crear snapshot nuevo, no reescribir el historial antiguo sin etiqueta. Procesamiento **at-least-once** con claves idempotentes, no prometer exactly-once global. Soft delete para fuentes; borrado irreversible de datos personales solo mediante proceso administrado con auditoría y políticas de retención.

## 5. Ejemplo de respuesta `/agendas/compare`
```json
{
  "window":"24h", "as_of":"2026-10-14T21:00:00Z",
  "unit":"share_of_observed_attention_pct",
  "source_health":{"own":"healthy","reference":"partial","public":"healthy"},
  "rows":[{"event_id":"evt_123","label":"Tema de ejemplo",
    "reference_share":31.5,"own_share":10.0,"gap_pp":21.5,
    "source_count":6,"confidence":0.82,"sample_caveat":"Solo medios configurados"}],
  "config_version":4,"algorithm_version":"salience-0.1"
}
```

Todos los ejemplos son sintéticos; no afirmar que miden noticias reales.
