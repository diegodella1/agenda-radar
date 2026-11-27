"""Unknown/manual evidence is internal by default. Notes never leave via this module."""
from sqlalchemy import select

from .models import Observation, Source


def permitted_evidence(session, evidence, destination, source_ids=None):
    if destination == 'internal' and not source_ids:
        return evidence
    allowed = []
    for item in evidence:
        sources = list(session.scalars(select(Source).join(
            Observation, Observation.source_id == Source.id
        ).where(Observation.document_id == item['id'])))
        if source_ids and not any(source.id in source_ids for source in sources):
            continue
        if destination == 'external' and (not sources or any(
            source.options.get('data_policy', 'internal') != 'external' for source in sources
        )):
            continue
        allowed.append(item)
    return allowed
