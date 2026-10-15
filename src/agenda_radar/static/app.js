'use strict';
const basePath = document.querySelector('meta[name="app-base"]')?.content || '';
const appUrl = path => basePath && !path.startsWith(basePath + '/') ? basePath + path : path;
const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
function notice(message, error = false) {
  const node = document.querySelector('#notice');
  node.hidden = false; node.textContent = message; node.className = error ? 'notice error' : 'notice';
}
async function api(path, body, method = 'POST') {
  const response = await fetch(appUrl(path), {method, credentials:'same-origin', headers:{
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
    if (form.hasAttribute('data-config')) {data={config:window.configEditor.read(),reason:data.reason};endpoint='/api/v1/admin/config/publish';}
    if (form.dataset.dynamicSource) {endpoint=`/api/v1/admin/sources/${data.source_id}/${form.dataset.dynamicSource}`;delete data.source_id;}
    if(form.hasAttribute('data-login') && data.email==='demo' && !basePath) endpoint='/demo/api/v1/auth/login';
    const result=await api(endpoint,data,form.dataset.method||'POST');
    if (form.hasAttribute('data-setup')) {location.href=appUrl('/login');return;}
    if (form.hasAttribute('data-login')) {location.href=result.redirect || (data.email==='demo' ? '/demo/' : appUrl('/'));return;}
    if (result.job_id) {displayResult(await jobResult(result.job_id));notice('Consulta completada.');}
    else {notice('Guardado.');location.reload();}
  } catch(error) {notice(error.message,true);} finally {if (button) button.disabled=false;}
});
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-action],[data-post]');if (!button) return;
  button.disabled=true;
  try {
    if(button.dataset.action==='demo-reset'){if(!confirm('¿Reiniciar tu escenario? Se borrarán únicamente tus cambios de esta demo.'))return;await api('/api/v1/demo/reset',{});location.href=appUrl('/');}
    else if(button.dataset.action==='demo-news'){const result=await api('/api/v1/demo/news',{});const message=result.already_applied?'Este lote ya fue aplicado. Reiniciá la demo para repetirlo.':`Se incorporaron ${result.documents_added} publicaciones ficticias y se generaron ${result.alerts_created} alertas. El radar está actualizado.`;sessionStorage.setItem('radar-demo-notice',message);sessionStorage.setItem('radar-demo-changes',JSON.stringify(result.affected_events || []));location.reload();}
    else if (button.dataset.post) {const result=await api(button.dataset.post,{});if(result.job_id)displayResult(await jobResult(result.job_id));else location.reload();}
    else if(button.dataset.action==='logout'){await api('/api/v1/auth/logout',{});location.href=appUrl('/login');}
    else if(button.dataset.action==='pair'){const result=await api('/api/v1/telegram/pair',{});notice(`Enviá al bot este comando dentro de 10 minutos: ${result.command}`);}
    else if(button.dataset.action==='test-source'){const data=payload(document.querySelector('#source-form'));const result=await api('/api/v1/admin/sources/test',data);displayResult(await jobResult(result.job_id));}
    else if(button.dataset.action==='preview-config'){const form=button.closest('form');if(!window.configEditor.validate())return;const draft=window.configEditor.read();const result=await api('/api/v1/admin/config/preview',{config:draft,reason:form.elements.reason.value||'Previsualización'});window.configEditor.preview(result,draft);notice('Previsualización calculada. La configuración activa no cambió.');}
  }catch(error){notice(error.message,true);}finally{button.disabled=false;}
});
for (const link of document.querySelectorAll('nav a')) if(link.pathname===location.pathname)link.setAttribute('aria-current','page');

document.querySelector('[data-readiness]')?.addEventListener('click', async () => {
  try {displayResult(await api('/api/v1/admin/readiness',undefined,'GET'), '#readiness-result');}
  catch(error) {notice(error.message,true);}
});

if(basePath==='/demo' && sessionStorage.getItem('radar-demo-notice')){notice(sessionStorage.getItem('radar-demo-notice'));sessionStorage.removeItem('radar-demo-notice');}

const helpDialog = document.querySelector('#editorial-help');
const helpSteps = [
  ['Detectar una señal', 'Elegí un período. Las tarjetas priorizan acontecimientos según tus fuentes y criterios editoriales; las barras comparan atención propia y de referencia.'],
  ['Entender y contrastar', 'Abrí Entender diferencia o una fila del gráfico. Contrastá medios, grupos independientes y publicaciones originales. Una brecha no demuestra que un tema esté escalando.'],
  ['Decidir y observar cambios', 'Desde Ver evidencia registrá Seguir, Revisar, Descartar o Aceptar y explicá el motivo. En demo, Simular novedades agrega publicaciones ficticias y enlaza los acontecimientos afectados.']
];
let helpStep = 0;
function renderHelp() {
  document.querySelector('#help-step').textContent = `Paso ${helpStep + 1} de 3`;
  document.querySelector('#help-title').textContent = helpSteps[helpStep][0];
  document.querySelector('#help-copy').textContent = helpSteps[helpStep][1];
  document.querySelector('[data-help-next]').textContent = helpStep === 2 ? 'Terminar' : 'Siguiente →';
}
for (const button of document.querySelectorAll('[data-help]')) button.addEventListener('click', () => {helpStep=0;renderHelp();helpDialog.showModal();});
document.querySelector('[data-help-close]')?.addEventListener('click', () => helpDialog.close());
document.querySelector('[data-help-next]')?.addEventListener('click', () => {if(helpStep===2)helpDialog.close();else{helpStep++;renderHelp();}});
document.addEventListener('keydown', event => {
  if(event.key !== 'Escape') return;
  const detail = document.activeElement?.closest('details[open]');
  if(detail){detail.open=false;detail.querySelector('summary').focus();}
});

if(basePath==='/demo' && sessionStorage.getItem('radar-demo-changes')) {
  try {
    const changes=JSON.parse(sessionStorage.getItem('radar-demo-changes'));
    const list=document.createElement('div');list.className='news-links';
    for(const change of changes){const link=document.createElement('a');link.href=appUrl(`/events/${Number(change.event_id)}?window=24h`);const percent=value=>value==null?'Sin datos':`${Number(value).toFixed(1)}%`;link.textContent=`${change.label}: referencias ${percent(change.before)} → ${percent(change.after)} · Ver evidencia`;list.append(link);}
    document.querySelector('#notice')?.append(list);
  } catch { /* An expired browser notice must not prevent normal navigation. */ }
  sessionStorage.removeItem('radar-demo-changes');
}

// Inline mobile navigation keeps the content reachable without an overlay or focus trap.
document.documentElement.classList.add('js');
const navToggle=document.querySelector('[data-nav-toggle]');
const workspaceNav=document.querySelector('#workspace-nav');
function setNavigation(open){
  workspaceNav?.classList.toggle('is-open',open);
  navToggle?.setAttribute('aria-expanded',String(open));
  navToggle?.setAttribute('aria-label',open?'Cerrar navegación':'Abrir navegación');
}
navToggle?.addEventListener('click',()=>setNavigation(navToggle.getAttribute('aria-expanded')!=='true'));
document.addEventListener('keydown',event=>{
  if(event.key==='Escape' && workspaceNav?.classList.contains('is-open') && !helpDialog?.open){setNavigation(false);navToggle.focus();}
});
