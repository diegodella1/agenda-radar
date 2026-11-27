const translate = (message, values) => globalThis.RadarI18n?.t(message, values) ?? message.replace(/\{(\w+)\}/g, (_, key) => values[key]);
const jobs = new Map();
export function jobResult(id, api, notice) {
  if (!jobs.has(id)) jobs.set(id, poll(id, api, notice).finally(() => jobs.delete(id)));
  return jobs.get(id);
}
async function poll(id, api, notice) {
  notice(translate('Trabajo #{id} en cola. El worker procesará la solicitud.',{id}));
  const deadline = Date.now() + 180000;
  let delay = 1500;
  while (Date.now() < deadline) {
    await new Promise(resolve => setTimeout(resolve, Math.min(delay, deadline-Date.now())));
    if (Date.now() >= deadline) break;
    const job = await api(`/api/v1/jobs/${id}`, undefined, 'GET');
    if (job.status === 'done') return job.result;
    if (job.status === 'failed') throw new Error(translate('Trabajo fallido: {code}',{code:job.error_code}));
    delay = Math.min(5000, delay * 1.5);
  }
  throw new Error(translate('El trabajo #{id} sigue pendiente. Revisá el worker en Operaciones.',{id}));
}
