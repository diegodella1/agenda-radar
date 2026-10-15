"""Optional extraction and ambiguous-event suggestions; human corrections remain authoritative."""

import json
import time

from pydantic import BaseModel, Field
from sqlalchemy import select

from .assistant import SYSTEM_PROMPT, reserve_budget, retrieve
from .editorial import active_config
from .models import APIUsage, Document, Mention, Prompt, State
from .security import audit


class ExtractedEntity(BaseModel):
    name: str
    evidence_span: str


class Extraction(BaseModel):
    document_id: int
    topic: str
    entities: list[ExtractedEntity]
    related_document_id: int | None
    reason: str
    confidence: float = Field(ge=0, le=1)


def enrich_document(db, vault, document_id, expected_hash, prompt_id=None, apply=True):
    with db.session() as session:
        _, config = active_config(session)
        document = session.get(Document, document_id)
        if not document or document.content_hash != expected_hash:
            return {"status": "superseded"}
        key = vault.get(session, "openai")
        if not config.ai_enabled or not config.extraction_enabled or not key:
            return {"status": "disabled"}
        mention = session.get(Mention, document_id)
        if mention and mention.human_verified:
            return {"status": "human_verified"}
        prompt = (
            session.get(Prompt, prompt_id)
            if prompt_id
            else session.scalar(
                select(Prompt)
                .where(Prompt.purpose == "extract_event", Prompt.status == "published")
                .order_by(Prompt.id.desc())
            )
        )
        candidates = [
            item
            for item in retrieve(session, document.title, window="72h")
            if item["id"] != document_id
        ][:6]
        original = {"id": document.id, "title": document.title, "excerpt": document.excerpt}
        model = config.extraction_model or config.ai_model
        if prompt and prompt.model != model:
            return {"status": "model_price_mismatch"}
    input_rate = config.extraction_input_usd_million
    output_rate = config.extraction_output_usd_million
    if not model or input_rate <= 0 or output_rate <= 0:
        return {"status": "pricing_required"}
    context = json.dumps(
        {
            "document": original,
            "candidates": candidates,
            "allowed_topics": list(config.topic_keywords),
        },
        ensure_ascii=False,
    )
    instructions = (
        SYSTEM_PROMPT
        + "\nExtraé entidades copiando spans literales. Sugerí un documento relacionado solo si describe el mismo hecho específico. Si hay duda, related_document_id=null."
    )
    if prompt:
        instructions += "\n" + prompt.template
    reservation = (
        (len(context.encode()) + len(instructions.encode()) + 3000) * input_rate
        + 1000 * output_rate
    ) / 1_000_000
    try:
        usage_id = reserve_budget(db, config, "extract_event", model, reservation)
    except ValueError:
        return {"status": "budget_exhausted"}
    from openai import OpenAI

    response = OpenAI(api_key=key, timeout=45, max_retries=0).responses.parse(
        model=model,
        instructions=instructions,
        input=context,
        text_format=Extraction,
        max_output_tokens=1000,
        store=False,
    )
    with db.session() as session:
        usage = session.get(APIUsage, usage_id)
        if response.usage:
            usage.input_tokens = response.usage.input_tokens
            usage.output_tokens = response.usage.output_tokens
            usage.cost_usd = (
                usage.input_tokens * input_rate + usage.output_tokens * output_rate
            ) / 1_000_000
            usage.status = "completed"
        result = response.output_parsed
        if not result or result.document_id != document_id:
            return {"status": "invalid_output"}
        document = session.get(Document, document_id)
        if not document or document.content_hash != expected_hash:
            return {"status": "superseded"}
        corpus = document.title + " " + document.excerpt
        valid_entities = [
            entity.model_dump()
            for entity in result.entities
            if entity.name
            and entity.name in entity.evidence_span
            and entity.evidence_span in corpus
        ]
        if not apply:
            return {
                "status": "tested",
                "entity_count": len(valid_entities),
                "result": result.model_dump(),
            }
        document.entities = valid_entities
        if result.topic in config.topic_keywords:
            document.topic = result.topic
        if result.related_document_id in {item["id"] for item in candidates}:
            related = session.get(Mention, result.related_document_id)
            own = session.get(Mention, document_id)
            if related and own and related.event_id != own.event_id and not own.human_verified:
                session.merge(
                    State(
                        key=f"event_review:{document_id}",
                        value={
                            "event_id": own.event_id,
                            "candidate_event_id": related.event_id,
                            "reason": result.reason,
                            "confidence": result.confidence,
                            "at": time.time(),
                        },
                    )
                )
        audit(
            session,
            None,
            "ai_enrichment",
            "document",
            document_id,
            after={"entity_count": len(valid_entities), "usage_id": usage_id},
        )
    return {"status": "enriched", "entity_count": len(valid_entities)}
