'use strict';
const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
function notice(message, error = false) {
  const node = document.querySelector('#notice');
  node.hidden = false; node.textContent = message; node.className = error ? 'notice error' : 'notice';
}
async function api(path, body, method = 'POST') {
  const response = await fetch(path, {method, credentials:'same-origin', headers:{
    'Content-Type':'application/json', 'X-Requested-With':'AgendaRadar', 'X-CSRF-Token':csrf()},
    ...(body === undefined ? {} : {body:JSON.stringify(body)})});
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail));
  return result;
}
function payload(form) {
  const result = Object.fromEntries(new FormData(form));
  for (const node of form.querySelectorAll('[data-number]')) result[node.name] = Number(node.value);
  for (const node of form.querySelectorAll('[data-timestamp]')) result[node.name] = new Date(node.value).getTime()/1000;
  for (const node of form.querySelectorAll('[data-number-list]')) result[node.name] = node.value.split(',').map(x=>Number(x.trim()));
  if (form.hasAttribute('data-json-form')) return JSON.parse(result.payload);
  return result;
}
async function jobResult(id) {
  notice(`Trabajo #${id} en cola. El worker procesará la solicitud.`);
  for (let attempt=0; attempt<120; attempt++) {
    await new Promise(resolve=>setTimeout(resolve,1500));
    const job = await api(`/api/v1/jobs/${id}`,undefined,'GET');
    if (job.status==='done') return job.result;
    if (job.status==='failed') throw new Error(`Trabajo fallido: ${job.error_code}`);
  }
  throw new Error(`El trabajo #${id} sigue pendiente. Revisá el worker en Operaciones.`);
}
function displayResult(result, selector='#query-result') {
  let target = document.querySelector(selector);
  if (!target) {target=document.createElement('section');document.querySelector('main').append(target);}
  target.replaceChildren();
  if (result.answer) {
    const p=document.createElement('p');p.className='answer';p.textContent=result.answer;target.append(p);
    for (const item of result.evidence || []) {const p=document.createElement('p');const a=document.createElement('a');a.textContent=item.title;a.href=item.url;a.target='_blank';a.rel='noopener noreferrer';p.append(a);target.append(p);}
    const small=document.createElement('p');small.textContent=(result.limitations||[]).join(' · ');small.className='caveat';target.append(small);
  } else {const pre=document.createElement('pre');pre.textContent=JSON.stringify(result,null,2);target.append(pre);}
}
document.addEventListener('submit', async event=>{
  const form=event.target;
  if (!form.matches('[data-endpoint],[data-config],[data-dynamic-source]')) return;
  event.preventDefault(); const button=form.querySelector('button[type="submit"],button:not([type])');
  if (button) button.disabled=true;
  try {
    let data=payload(form), endpoint=form.dataset.endpoint;
    if (form.hasAttribute('data-config')) {data={config:JSON.parse(data.config),reason:data.reason};endpoint='/api/v1/admin/config/publish';}
    if (form.dataset.dynamicSource) {endpoint=`/api/v1/admin/sources/${data.source_id}/${form.dataset.dynamicSource}`;delete data.source_id;}
    const result=await api(endpoint,data,form.dataset.method||'POST');
    if (form.hasAttribute('data-setup')) {location.href='/login';return;}
    if (form.hasAttribute('data-login')) {location.href='/';return;}
    if (result.job_id) {displayResult(await jobResult(result.job_id));notice('Consulta completada.');}
    else {notice('Guardado.');location.reload();}
  } catch(error) {notice(error.message,true);} finally {if (button) button.disabled=false;}
});
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-action],[data-post]');if (!button) return;
  button.disabled=true;
  try {
    if (button.dataset.post) {const result=await api(button.dataset.post,{});if(result.job_id)displayResult(await jobResult(result.job_id));else location.reload();}
    else if(button.dataset.action==='logout'){await api('/api/v1/auth/logout',{});location.href='/login';}
    else if(button.dataset.action==='pair'){const result=await api('/api/v1/telegram/pair',{});notice(`Enviá al bot este comando dentro de 10 minutos: ${result.command}`);}
    else if(button.dataset.action==='test-source'){const data=payload(document.querySelector('#source-form'));const result=await api('/api/v1/admin/sources/test',data);displayResult(await jobResult(result.job_id));}
    else if(button.dataset.action==='preview-config'){const data=payload(button.closest('form'));const result=await api('/api/v1/admin/config/preview',{config:JSON.parse(data.config),reason:data.reason||'Previsualización'});const target=document.querySelector('#preview-result');target.hidden=false;target.textContent=JSON.stringify(result,null,2);notice('Previsualización calculada. La configuración activa no cambió.');}
  }catch(error){notice(error.message,true);}finally{button.disabled=false;}
});
for (const link of document.querySelectorAll('nav a')) if(link.pathname===location.pathname)link.setAttribute('aria-current','page');

document.addEventListener('change',event=>{
  const field=event.target.dataset.configField;if(!field)return;
  const textarea=event.target.closest('form').querySelector('textarea[name="config"]');
  try{const config=JSON.parse(textarea.value);config[field]=Number(event.target.value);textarea.value=JSON.stringify(config,null,2);}catch(error){notice('Corregí el JSON antes de modificar controles.',true);}
});

document.querySelector('[data-readiness]')?.addEventListener('click', async () => {
  try {displayResult(await api('/api/v1/admin/readiness',undefined,'GET'), '#readiness-result');}
  catch(error) {notice(error.message,true);}
});
