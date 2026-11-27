'use strict';
const basePath = document.querySelector('meta[name="app-base"]')?.content || '';
const appUrl = path => basePath && !path.startsWith(basePath + '/') ? basePath + path : path;
const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
function notice(message, error = false) {
  const node = document.querySelector('#notice');
  node.hidden = false; node.textContent = window.RadarI18n.t(message); node.className = error ? 'notice error' : 'notice';
  const close=document.createElement('button');
  close.type='button';close.className='notice-close';close.textContent='×';
  close.setAttribute('aria-label',window.RadarI18n.t('Cerrar aviso'));
  close.addEventListener('click',()=>{node.hidden=true;});
  node.append(close);
}
const pendingReads = new Map();
function api(path, body, method = 'POST') {
  const key = appUrl(path);
  if (method !== 'GET') return request(path, body, method);
  if (!pendingReads.has(key)) {
    pendingReads.set(key, request(path, body, method).finally(() => pendingReads.delete(key)));
  }
  return pendingReads.get(key);
}
async function request(path, body, method) {
  const response = await fetch(appUrl(path), {method, credentials:'same-origin', headers:{
    'Content-Type':'application/json', 'X-Requested-With':'AgendaRadar', 'X-CSRF-Token':csrf()},
    ...(body === undefined ? {} : {body:JSON.stringify(body)})});
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    throw new Error(window.RadarI18n.t('El servidor no pudo completar la solicitud (HTTP {status}). Esperá unos segundos y volvé a intentar.',{status:response.status}));
  }
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
  const module = await loadFeature('jobs');
  return module.jobResult(id, api, notice);
}
function displayResult(result, selector='#query-result') {
  let target = document.querySelector(selector);
  if (!target) {target=document.createElement('section');document.querySelector('main').append(target);}
  target.replaceChildren();
  if (result.answer) {
    const p=document.createElement('p');p.className='answer';p.textContent=window.RadarI18n.t(result.answer);target.append(p);
    for (const item of result.evidence || []) {const p=document.createElement('p');const a=document.createElement('a');a.textContent=item.title;a.href=item.url;a.target='_blank';a.rel='noopener noreferrer';p.append(a);target.append(p);}
    const small=document.createElement('p');small.textContent=(result.limitations||[]).map(window.RadarI18n.t).join(' · ');small.className='caveat';target.append(small);
  } else {const pre=document.createElement('pre');pre.textContent=JSON.stringify(result,null,2);target.append(pre);}
}
document.addEventListener('submit', async event=>{
  const form=event.target;
  if (!form.matches('[data-endpoint],[data-config],[data-dynamic-source]')) return;
  event.preventDefault();
  if (form.dataset.pending) return;
  form.dataset.pending='true';
  const button=form.querySelector('button[type="submit"],button:not([type])');
  if (button) button.disabled=true;
  try {
    let data=payload(form), endpoint=form.dataset.endpoint;
    if (form.hasAttribute('data-config')) {data={config:window.configEditor.read(),reason:data.reason};endpoint='/api/v1/admin/config/publish';}
    if (form.dataset.dynamicSource) {endpoint=`/api/v1/admin/sources/${data.source_id}/${form.dataset.dynamicSource}`;delete data.source_id;}
    if(form.hasAttribute('data-login') && data.email==='demo' && !basePath && form.dataset.showcase==='true'){location.href='/demo/';return;}
    if(form.hasAttribute('data-login') && data.email==='demo' && !basePath) endpoint='/demo/api/v1/auth/login';
    let result=await api(endpoint,data,form.dataset.method||'POST');
    while (form.hasAttribute('data-login') && result.pending) {
      notice(result.detail);
      await new Promise(resolve=>setTimeout(resolve,2000));
      result=await api(endpoint,data);
    }
    if (form.hasAttribute('data-setup')) {location.href=appUrl('/login');return;}
    if (form.hasAttribute('data-login')) {
      let redirect=result.redirect || (data.email==='demo' ? '/demo/' : appUrl('/'));
      const next=new URLSearchParams(location.search).get('next');
      if(data.email!=='demo' && next && next.startsWith('/') && !next.startsWith('//')) {
        const destination=new URL(next,location.origin);
        if(destination.origin===location.origin && destination.pathname==='/collaboration')
          redirect=destination.pathname+destination.search;
      }
      if(data.email==='demo') {
        try {sessionStorage.setItem('radar-demo-tour',JSON.stringify({version:1,status:'active',step:0,eventUrl:null}));}
        catch {redirect='/demo/?tour=0';}
      }
      location.href=redirect;return;
    }
    if (result.job_id) {displayResult(await jobResult(result.job_id));notice(window.RadarI18n.t('Consulta completada.'));}
    else {notice(window.RadarI18n.t('Guardado.'));location.reload();}
  } catch(error) {notice(error.message,true);} finally {delete form.dataset.pending;if (button) button.disabled=false;}
});
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-action],[data-post]');if (!button || button.disabled) return;
  button.disabled=true;
  try {
    if(button.dataset.action==='demo-reset'){if(!confirm(window.RadarI18n.t('¿Reiniciar tu escenario? Se borrarán únicamente tus cambios de esta demo.')))return;await api('/api/v1/demo/reset',{});location.href=appUrl('/');}
    else if(button.dataset.action==='demo-news'){const result=await api('/api/v1/demo/news',{});const message=result.already_applied?window.RadarI18n.t('Sin novedades desde la última captura.'):`Se incorporaron ${result.documents_added} publicaciones reales y se generaron ${result.alerts_created} alertas. El radar está actualizado.`;sessionStorage.setItem('radar-demo-notice',message);sessionStorage.setItem('radar-demo-changes',JSON.stringify(result.affected_events || []));location.reload();}
    else if (button.dataset.post) {const result=await api(button.dataset.post,{});if(result.job_id)displayResult(await jobResult(result.job_id));else location.reload();}
    else if(button.dataset.action==='logout'){await api('/api/v1/auth/logout',{});if(basePath==='/demo'){try{sessionStorage.removeItem('radar-demo-tour');}catch{}}location.href=appUrl('/login');}
    else if(button.dataset.action==='pair'){const result=await api('/api/v1/telegram/pair',{});notice(window.RadarI18n.t('Enviá al bot este comando dentro de 10 minutos: {command}',{command:result.command}));}
    else if(button.dataset.action==='test-source'){const data=payload(document.querySelector('#source-form'));const result=await api('/api/v1/admin/sources/test',data);displayResult(await jobResult(result.job_id));}
    else if(button.dataset.action==='preview-config'){const form=button.closest('form');if(!window.configEditor.validate())return;const draft=window.configEditor.read();const result=await api('/api/v1/admin/config/preview',{config:draft,reason:form.elements.reason.value||window.RadarI18n.t('Previsualización')});window.configEditor.preview(result,draft);notice(window.RadarI18n.t('Previsualización calculada. La configuración activa no cambió.'));}
  }catch(error){notice(error.message,true);}finally{button.disabled=false;}
});
for (const link of document.querySelectorAll('nav a')) if(link.pathname===location.pathname)link.setAttribute('aria-current','page');

document.querySelector('[data-readiness]')?.addEventListener('click', async event => {
  const button=event.currentTarget;
  if(button.disabled)return;
  button.disabled=true;
  try {displayResult(await api('/api/v1/admin/readiness',undefined,'GET'), '#readiness-result');}
  catch(error) {notice(error.message,true);}
  finally {button.disabled=false;}
});

try {if(basePath==='/demo' && sessionStorage.getItem('radar-demo-notice')){notice(sessionStorage.getItem('radar-demo-notice'));sessionStorage.removeItem('radar-demo-notice');}} catch { /* Browser storage may be unavailable. */ }

document.addEventListener('keydown', event => {
  if(event.key !== 'Escape') return;
  const detail = document.activeElement?.closest('details[open]');
  if(detail){detail.open=false;detail.querySelector('summary').focus();}
});

try {if(basePath==='/demo' && sessionStorage.getItem('radar-demo-changes')) {
  try {
    const changes=JSON.parse(sessionStorage.getItem('radar-demo-changes'));
    const list=document.createElement('div');list.className='news-links';
    for(const change of changes){const link=document.createElement('a');link.href=appUrl(`/events/${Number(change.event_id)}?window=24h`);const percent=value=>value==null?window.RadarI18n.t('Sin datos'):`${Number(value).toFixed(1)}%`;link.textContent=`${change.label}: referencias ${percent(change.before)} → ${percent(change.after)} · Ver evidencia`;list.append(link);}
    document.querySelector('#notice')?.append(list);
  } catch { /* An expired browser notice must not prevent normal navigation. */ }
  sessionStorage.removeItem('radar-demo-changes');
}} catch { /* The rest of the interface works without browser storage. */ }

// Inline mobile navigation keeps the content reachable without an overlay or focus trap.

const navToggle=document.querySelector('[data-nav-toggle]');
const workspaceNav=document.querySelector('#workspace-nav');
function setNavigation(open){
  workspaceNav?.classList.toggle('is-open',open);
  navToggle?.setAttribute('aria-expanded',String(open));
  navToggle?.setAttribute('aria-label',open?window.RadarI18n.t('Cerrar navegación'):window.RadarI18n.t('Abrir navegación'));
}
navToggle?.addEventListener('click',()=>setNavigation(navToggle.getAttribute('aria-expanded')!=='true'));
document.addEventListener('keydown',event=>{
  if(event.key==='Escape' && workspaceNav?.classList.contains('is-open') && !document.querySelector('dialog[open]')){setNavigation(false);navToggle.focus();}
});

const features = new Map();
function loadFeature(name) {
  if (!features.has(name)) {
    const url = document.querySelector(`meta[name="feature-${name}"]`).content;
    features.set(name, import(url).catch(error => {features.delete(name);throw error;}));
  }
  return features.get(name);
}
for (const button of document.querySelectorAll('[data-help]')) button.addEventListener('click', async () => {
  if(button.disabled)return;
  button.disabled=true;
  try {
    if(basePath==='/demo') (await loadFeature('onboarding')).startTour(button);
    else (await loadFeature('help')).openHelp();
  } catch(error) {notice(error.message,true);}
  finally {button.disabled=false;}
});
if(basePath==='/demo') {
  let active = new URLSearchParams(location.search).has('tour');
  try {active ||= JSON.parse(sessionStorage.getItem('radar-demo-tour'))?.status === 'active';} catch {}
  if(active) loadFeature('onboarding').catch(error=>notice(error.message,true));
}
