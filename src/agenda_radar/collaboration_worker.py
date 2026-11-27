"""Separate execution lane: slow models cannot block news collection or Slack receipt."""
import asyncio
import fcntl
import logging
import re
import time
import uuid

from pydantic import BaseModel
from sqlalchemy import select

from .agents import due_agents, run_agent, slack_config
from .collaboration_models import AIProfile, ChannelDelivery
from .db import Database
from .jobs import claim, enqueue, finish, renew
from .models import State, User
from .security import ROLES, Vault
from .slack_connector import answer_slack, deliver_one, socket_client, test_connection

COLLABORATION_JOBS = ('query', 'telegram_query', 'enrich', 'test_prompt', 'model_test',
                      'slack_test', 'slack_query', 'agent_run', 'agent_preview')
log = logging.getLogger('agenda.collaboration')


class ConnectionProbe(BaseModel):
    message: str


def execute(db, vault, settings, job):
    if job.user_id:
        with db.session() as session:
            user = session.get(User, job.user_id)
            minimum = 'superadmin' if job.kind in ('model_test', 'slack_test', 'test_prompt') else 'media_admin' if job.kind == 'agent_preview' else 'editor'
            if not user or not user.enabled or ROLES[user.role] < ROLES[minimum]:
                raise ValueError('user_permission_revoked')
    if job.kind in ('agent_run', 'agent_preview'):
        return run_agent(db, vault, job.payload['agent_id'], preview=job.kind == 'agent_preview')
    if job.kind == 'model_test':
        from .ai import generate
        from .collaboration_api import record
        from .security import digest
        with db.session() as session:
            profile_before = record(session.get(AIProfile, job.payload['profile_id']))
            key_before = digest(vault.get(session, f"ai:{job.payload['profile_id']}") or '')
        result, run_id = generate(db, vault, job.payload['profile_id'], 'connection_test',
            'Return a JSON object with message set to OK. This is a synthetic capability test.', {}, ConnectionProbe, testing=True)
        if result.message != 'OK':
            raise ValueError('model_capability_test_failed')
        with db.session() as session:
            profile = session.get(AIProfile, job.payload['profile_id'])
            if record(profile) != profile_before or digest(vault.get(session, f'ai:{profile.id}') or '') != key_before:
                raise ValueError('profile_changed_during_test')
            profile.tested_at = time.time()
        return {'ok': True, 'ai_run_id': run_id}
    if job.kind == 'slack_test':
        return test_connection(db, vault)
    if job.kind == 'slack_query':
        return answer_slack(db, vault, settings, job)
    from .worker import execute_job
    result = execute_job(db, vault, settings, job)
    if job.kind == 'telegram_query':
        from .telegram_bot import Telegram
        asyncio.run(Telegram(db, vault).call('sendMessage', {'chat_id': job.payload['chat_id'],
            'text': (result['answer']+'\n'+'\n'.join(item['url'] for item in result['evidence'][:5]))[:4000]}))
    return result


async def run(settings):
    db, vault = Database(settings.database_path), Vault(settings.secrets_dir)
    lock = (settings.data_dir / 'collaboration.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    owner = str(uuid.uuid4())
    socket, fingerprint = None, None
    # An interrupted send can already exist remotely. Surface it for review rather than repost.
    with db.session() as session:
        for delivery in session.scalars(select(ChannelDelivery).where(ChannelDelivery.status == 'sending')):
            delivery.status, delivery.error_code = 'failed', 'interrupted_send_unknown'

    async def control_loop():
        nonlocal socket, fingerprint
        while True:
            try:
                with db.session() as session:
                    config = slack_config(session)
                    from .security import digest
                    current = digest(str(config)+str(vault.get(session, 'slack_app'))+str(vault.get(session, 'slack_bot')))
                    session.merge(State(key='collaboration_heartbeat', value={'at': time.time(), 'slack_enabled': config.get('enabled', False)}))
                if current != fingerprint:
                    if socket:
                        await asyncio.to_thread(socket.close)
                        socket = None
                    if config.get('enabled'):
                        socket = await asyncio.to_thread(socket_client, db, vault)
                        await asyncio.to_thread(socket.connect)
                    fingerprint = current
                for agent_id in await asyncio.to_thread(due_agents, db):
                    enqueue(db, 'agent_run', {'agent_id': agent_id}, f'agent:{agent_id}:{int(time.time()//300)}')
            except Exception:
                log.warning('collaboration_control_failed')
            await asyncio.sleep(5)

    async def delivery_loop():
        while True:
            try:
                await asyncio.to_thread(deliver_one, db, vault, settings)
            except Exception:
                log.warning('collaboration_delivery_failed')
            await asyncio.sleep(3)

    async def lease_loop(identifier):
        while True:
            await asyncio.sleep(30)
            await asyncio.to_thread(renew, db, identifier, owner)

    tasks = [asyncio.create_task(control_loop()), asyncio.create_task(delivery_loop())]
    try:
        while True:
            job = await asyncio.to_thread(claim, db, owner, kinds=COLLABORATION_JOBS)
            if not job:
                await asyncio.sleep(2)
                continue
            lease = asyncio.create_task(lease_loop(job.id))
            try:
                result = await asyncio.to_thread(execute, db, vault, settings, job)
                await asyncio.to_thread(finish, db, job.id, owner, result)
            except Exception as exc:
                code = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r'[a-z_0-9]{1,80}', str(exc)) else 'collaboration_job_failed'
                await asyncio.to_thread(finish, db, job.id, owner, error=code)
            finally:
                lease.cancel()
    finally:
        for task in tasks:
            task.cancel()
        if socket:
            await asyncio.to_thread(socket.close)
        lock.close()
