"""Frozen initial schema: independent of future ORM model changes."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

STATEMENTS = [
    "\nCREATE TABLE api_usage (\n\tid INTEGER NOT NULL, \n\tat FLOAT NOT NULL, \n\toperation VARCHAR NOT NULL, \n\tmodel VARCHAR NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\treserved_usd FLOAT NOT NULL, \n\tcost_usd FLOAT NOT NULL, \n\tinput_tokens INTEGER NOT NULL, \n\toutput_tokens INTEGER NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n",
    "CREATE INDEX ix_api_usage_at ON api_usage (at)",
    "\nCREATE TABLE documents (\n\tid INTEGER NOT NULL, \n\tpublisher VARCHAR(200) NOT NULL, \n\tgroup_name VARCHAR(200) NOT NULL, \n\tcanonical_url TEXT NOT NULL, \n\ttitle TEXT NOT NULL, \n\texcerpt TEXT NOT NULL, \n\tcontent_hash VARCHAR(64) NOT NULL, \n\tpublished_at FLOAT, \n\tobserved_at FLOAT NOT NULL, \n\tingested_at FLOAT NOT NULL, \n\tchannel VARCHAR NOT NULL, \n\ttopic VARCHAR NOT NULL, \n\tentities JSON NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (publisher, canonical_url)\n)\n\n",
    "CREATE INDEX ix_documents_observed_at ON documents (observed_at)",
    "CREATE INDEX ix_documents_published_at ON documents (published_at)",
    "\nCREATE TABLE events (\n\tid INTEGER NOT NULL, \n\tlabel TEXT NOT NULL, \n\ttopic VARCHAR NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\tfirst_observed_at FLOAT NOT NULL, \n\tconfidence FLOAT NOT NULL, \n\tparent_event_id INTEGER, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(parent_event_id) REFERENCES events (id)\n)\n\n",
    "\nCREATE TABLE prompts (\n\tid INTEGER NOT NULL, \n\tpurpose VARCHAR NOT NULL, \n\ttemplate TEXT NOT NULL, \n\tmodel VARCHAR NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\ttest_result JSON NOT NULL, \n\tat FLOAT NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n",
    "\nCREATE TABLE secrets (\n\tname VARCHAR NOT NULL, \n\tencrypted TEXT NOT NULL, \n\tPRIMARY KEY (name)\n)\n\n",
    "\nCREATE TABLE sources (\n\tid INTEGER NOT NULL, \n\tname VARCHAR(200) NOT NULL, \n\tkind VARCHAR(30) NOT NULL, \n\tchannel VARCHAR(30) NOT NULL, \n\turl TEXT NOT NULL, \n\tscope VARCHAR(20) NOT NULL, \n\tgroup_name VARCHAR(200) NOT NULL, \n\tweight FLOAT NOT NULL, \n\tcountry VARCHAR(10) NOT NULL, \n\tlegal_basis TEXT NOT NULL, \n\tenabled BOOLEAN NOT NULL, \n\tpoll_interval INTEGER NOT NULL, \n\tlast_success FLOAT, \n\tnext_poll FLOAT NOT NULL, \n\tstatus VARCHAR(40) NOT NULL, \n\terror_code VARCHAR(80), \n\tetag TEXT, \n\tmodified TEXT, \n\toptions JSON NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n",
    "CREATE INDEX ix_sources_next_poll ON sources (next_poll)",
    '\nCREATE TABLE state (\n\t"key" VARCHAR NOT NULL, \n\tvalue JSON NOT NULL, \n\tPRIMARY KEY ("key")\n)\n\n',
    "\nCREATE TABLE users (\n\tid INTEGER NOT NULL, \n\temail VARCHAR(254) NOT NULL, \n\tpassword_hash TEXT NOT NULL, \n\trole VARCHAR(30) NOT NULL, \n\tenabled BOOLEAN NOT NULL, \n\tcreated_at FLOAT NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (email)\n)\n\n",
    "\nCREATE TABLE alerts (\n\tid INTEGER NOT NULL, \n\tevent_id INTEGER NOT NULL, \n\trule VARCHAR NOT NULL, \n\tdedupe_key VARCHAR NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\tat FLOAT NOT NULL, \n\tpayload JSON NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(event_id) REFERENCES events (id), \n\tUNIQUE (dedupe_key)\n)\n\n",
    "CREATE INDEX ix_alerts_at ON alerts (at)",
    '\nCREATE TABLE audit_log (\n\tid INTEGER NOT NULL, \n\tactor_id INTEGER, \n\taction VARCHAR(100) NOT NULL, \n\tobject_kind VARCHAR(40) NOT NULL, \n\tobject_id VARCHAR(100) NOT NULL, \n\t"before" JSON NOT NULL, \n\t"after" JSON NOT NULL, \n\tat FLOAT NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(actor_id) REFERENCES users (id)\n)\n\n',
    "CREATE INDEX ix_audit_log_at ON audit_log (at)",
    "\nCREATE TABLE config_versions (\n\tid INTEGER NOT NULL, \n\tpayload JSON NOT NULL, \n\tcreated_by INTEGER, \n\tat FLOAT NOT NULL, \n\treason TEXT NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(created_by) REFERENCES users (id)\n)\n\n",
    "\nCREATE TABLE decisions (\n\tid INTEGER NOT NULL, \n\tevent_id INTEGER NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\taction VARCHAR NOT NULL, \n\treason TEXT NOT NULL, \n\tat FLOAT NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(event_id) REFERENCES events (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)\n\n",
    "CREATE INDEX ix_decisions_event_id ON decisions (event_id)",
    "\nCREATE TABLE document_versions (\n\tid INTEGER NOT NULL, \n\tdocument_id INTEGER NOT NULL, \n\ttitle TEXT NOT NULL, \n\texcerpt TEXT NOT NULL, \n\tcontent_hash VARCHAR(64) NOT NULL, \n\tobserved_at FLOAT NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(document_id) REFERENCES documents (id)\n)\n\n",
    "CREATE INDEX ix_document_versions_document_id ON document_versions (document_id)",
    "\nCREATE TABLE event_mentions (\n\tdocument_id INTEGER NOT NULL, \n\tevent_id INTEGER NOT NULL, \n\tsimilarity FLOAT NOT NULL, \n\thuman_verified BOOLEAN NOT NULL, \n\tmethod VARCHAR NOT NULL, \n\tPRIMARY KEY (document_id), \n\tFOREIGN KEY(document_id) REFERENCES documents (id), \n\tFOREIGN KEY(event_id) REFERENCES events (id)\n)\n\n",
    "CREATE INDEX ix_event_mentions_event_id ON event_mentions (event_id)",
    "\nCREATE TABLE ingest_runs (\n\tid INTEGER NOT NULL, \n\tsource_id INTEGER NOT NULL, \n\tstarted_at FLOAT NOT NULL, \n\tended_at FLOAT, \n\tstatus VARCHAR NOT NULL, \n\tcount INTEGER NOT NULL, \n\terror_code VARCHAR, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(source_id) REFERENCES sources (id)\n)\n\n",
    "CREATE INDEX ix_ingest_runs_source_id ON ingest_runs (source_id)",
    "\nCREATE TABLE jobs (\n\tid INTEGER NOT NULL, \n\tkind VARCHAR NOT NULL, \n\tpayload JSON NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\tattempt INTEGER NOT NULL, \n\trun_after FLOAT NOT NULL, \n\tlease_until FLOAT NOT NULL, \n\towner VARCHAR, \n\tidempotency_key VARCHAR NOT NULL, \n\terror_code VARCHAR, \n\tresult JSON NOT NULL, \n\tuser_id INTEGER, \n\tPRIMARY KEY (id), \n\tUNIQUE (idempotency_key), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)\n\n",
    "CREATE INDEX ix_jobs_status_run_after ON jobs (status, run_after)",
    "\nCREATE TABLE observations (\n\tid INTEGER NOT NULL, \n\tsource_id INTEGER NOT NULL, \n\tdocument_id INTEGER NOT NULL, \n\texternal_id TEXT NOT NULL, \n\tobserved_at FLOAT NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (source_id, external_id), \n\tFOREIGN KEY(source_id) REFERENCES sources (id), \n\tFOREIGN KEY(document_id) REFERENCES documents (id)\n)\n\n",
    "CREATE INDEX ix_observations_document_id ON observations (document_id)",
    "CREATE INDEX ix_observations_source_id ON observations (source_id)",
    "\nCREATE TABLE own_coverage (\n\tid INTEGER NOT NULL, \n\tevent_id INTEGER NOT NULL, \n\turl TEXT NOT NULL, \n\tchannel VARCHAR NOT NULL, \n\tpublished_at FLOAT NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(event_id) REFERENCES events (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)\n\n",
    "CREATE INDEX ix_own_coverage_event_id ON own_coverage (event_id)",
    "\nCREATE TABLE sessions (\n\ttoken_hash VARCHAR(64) NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tcsrf VARCHAR(128) NOT NULL, \n\texpires_at FLOAT NOT NULL, \n\tPRIMARY KEY (token_hash), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)\n\n",
    "CREATE INDEX ix_sessions_expires_at ON sessions (expires_at)",
    "\nCREATE TABLE telegram_links (\n\tuser_id INTEGER NOT NULL, \n\tchat_id INTEGER, \n\tcode_hash VARCHAR, \n\texpires_at FLOAT NOT NULL, \n\tmuted_until FLOAT NOT NULL, \n\tPRIMARY KEY (user_id), \n\tFOREIGN KEY(user_id) REFERENCES users (id), \n\tUNIQUE (chat_id), \n\tUNIQUE (code_hash)\n)\n\n",
    "\nCREATE TABLE trend_samples (\n\tid INTEGER NOT NULL, \n\tsource_id INTEGER NOT NULL, \n\tlabel TEXT NOT NULL, \n\tgeo VARCHAR NOT NULL, \n\tvalue VARCHAR, \n\tunit VARCHAR NOT NULL, \n\tcaptured_at FLOAT NOT NULL, \n\tsource_url TEXT NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (source_id, label, captured_at), \n\tFOREIGN KEY(source_id) REFERENCES sources (id)\n)\n\n",
    "CREATE INDEX ix_trend_samples_captured_at ON trend_samples (captured_at)",
    "\nCREATE TABLE notifications (\n\tid INTEGER NOT NULL, \n\talert_id INTEGER NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\tattempt INTEGER NOT NULL, \n\trun_after FLOAT NOT NULL, \n\texpires_at FLOAT NOT NULL, \n\tsent_at FLOAT, \n\terror_code VARCHAR, \n\tPRIMARY KEY (id), \n\tUNIQUE (alert_id, user_id), \n\tFOREIGN KEY(alert_id) REFERENCES alerts (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)\n\n",
    "\nCREATE TABLE score_snapshots (\n\tid INTEGER NOT NULL, \n\tevent_id INTEGER NOT NULL, \n\twindow VARCHAR NOT NULL, \n\tas_of FLOAT NOT NULL, \n\tconfig_version INTEGER NOT NULL, \n\talgorithm_version VARCHAR NOT NULL, \n\tpayload JSON NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(event_id) REFERENCES events (id), \n\tFOREIGN KEY(config_version) REFERENCES config_versions (id)\n)\n\n",
    "CREATE INDEX ix_score_snapshots_as_of ON score_snapshots (as_of)",
    "CREATE INDEX ix_score_snapshots_event_id ON score_snapshots (event_id)",
]
TABLES = [
    "api_usage",
    "documents",
    "events",
    "prompts",
    "secrets",
    "sources",
    "state",
    "users",
    "alerts",
    "audit_log",
    "config_versions",
    "decisions",
    "document_versions",
    "event_mentions",
    "ingest_runs",
    "jobs",
    "observations",
    "own_coverage",
    "sessions",
    "telegram_links",
    "trend_samples",
    "notifications",
    "score_snapshots",
]


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)
    op.execute(
        "CREATE VIRTUAL TABLE document_fts USING fts5(title, excerpt, content='documents', content_rowid='id', tokenize='unicode61 remove_diacritics 2')"
    )
    op.execute("""CREATE TRIGGER documents_ai AFTER INSERT ON documents BEGIN
      INSERT INTO document_fts(rowid,title,excerpt) VALUES(new.id,new.title,new.excerpt); END""")
    op.execute("""CREATE TRIGGER documents_ad AFTER DELETE ON documents BEGIN
      INSERT INTO document_fts(document_fts,rowid,title,excerpt) VALUES('delete',old.id,old.title,old.excerpt); END""")
    op.execute("""CREATE TRIGGER documents_au AFTER UPDATE ON documents BEGIN
      INSERT INTO document_fts(document_fts,rowid,title,excerpt) VALUES('delete',old.id,old.title,old.excerpt);
      INSERT INTO document_fts(rowid,title,excerpt) VALUES(new.id,new.title,new.excerpt); END""")


def downgrade():
    for name in ("documents_ai", "documents_ad", "documents_au"):
        op.execute(f"DROP TRIGGER {name}")
    op.execute("DROP TABLE document_fts")
    for name in reversed(TABLES):
        op.drop_table(name)
