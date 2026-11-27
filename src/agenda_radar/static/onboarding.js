'use strict';
let restartTour;
export function startTour(button) {restartTour(button);}
(() => {
  const dialog = document.querySelector('#demo-tour');
  if (!dialog) return;
  const storageKey = 'radar-demo-tour';
  const card = dialog.querySelector('.tour-card');
  const spotlight = dialog.querySelector('.tour-spotlight');
  const heading = dialog.querySelector('#tour-title');
  const copy = dialog.querySelector('#tour-copy');
  const note = dialog.querySelector('#tour-note');
  const checklist = dialog.querySelector('#tour-checklist');
  const next = dialog.querySelector('[data-tour-next]');
  const back = dialog.querySelector('[data-tour-back]');
  const steps = [
    {title: 'Conocé tu radar editorial', path: '/demo/',
      copy: 'Te mostramos dónde cargar fuentes, definir criterios y tomar decisiones. Horizonte Federal es un cliente ficticio; las fuentes y noticias son reales. La cobertura propia es simulada.'},
    {title: 'Primero, cargá tus fuentes', path: '/demo/admin/sources', target: 'sources',
      copy: 'Acá agregás los medios, feeds y cuentas que querés seguir. Definí cuáles son propios, cuáles son referencias y a qué grupo editorial pertenecen. Más abajo ya tenés el catálogo argentino y sus perfiles oficiales.'},
    {title: 'Definí tus criterios editoriales', path: '/demo/admin/config', target: 'criteria',
      copy: 'Elegí qué temas importan para tu medio y ajustá su peso. También podés ponderar fuentes, lugares y personas. La demo ya tiene criterios cargados: podés explorarlos sin cambiar nada.'},
    {title: 'Compará antes de publicar', path: '/demo/admin/config', target: 'preview',
      copy: 'Después de ajustar los criterios, compará el resultado con la versión activa. Cuando estés conforme, escribí un motivo y publicá la versión. Durante este recorrido no se guarda ningún cambio.'},
    {title: 'Leé las prioridades de tu agenda', path: '/demo/', target: 'radar',
      copy: 'Estas señales combinan tus criterios con las publicaciones observadas. Las barras comparan la atención propia y la de los medios de referencia. Usá el período y los filtros para enfocar la lectura.'},
    {title: 'Contrastá con las tendencias', path: '/demo/trends', target: 'trends',
      copy: 'Google Trends muestra interés de búsqueda en Argentina. Las redes aportan otra señal cuando están conectadas. Búsquedas, conversación y cobertura periodística se leen por separado.'},
    {title: 'Revisá la evidencia', target: 'evidence',
      copy: 'Cada acontecimiento reúne publicaciones y enlaces originales. Contrastá los medios, las fechas y los grupos independientes antes de decidir. La confianza indica calidad de agrupación, no veracidad.'},
    {title: 'Dejá una decisión para el equipo', target: 'decision',
      copy: 'Podés seguir, revisar, descartar o aceptar una recomendación y dejar el motivo. Registrar una decisión no publica contenido. Tus cambios en esta demo son privados.'},
    {title: '', path: '/demo/', copy: ''}
  ];
  let target = null, frame = 0, renderId = 0, opener = null;
  const initial = () => ({version:1, status:'active', step:0, eventUrl:null});
  function eventUrl(value) {
    if (typeof value !== 'string') return null;
    try {
      const url = new URL(value, location.origin);
      return url.origin === location.origin && /^\/demo\/events\/\d+$/.test(url.pathname)
        ? url.pathname + url.search : null;
    } catch { return null; }
  }
  const validStep = value => Number.isInteger(value) && value >= 0 && value < steps.length;
  function readState() {
    const params = new URL(location.href).searchParams;
    if (params.has('tour') && /^\d+$/.test(params.get('tour')) && validStep(Number(params.get('tour')))) {
      return {...initial(), step:Number(params.get('tour')), eventUrl:eventUrl(params.get('tour-event'))};
    }
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey));
      if (saved?.version === 1 && validStep(saved.step) && ['active','completed','skipped'].includes(saved.status)) {
        return {...saved, eventUrl:eventUrl(saved.eventUrl)};
      }
    } catch { /* Storage can be disabled or an older entry can be invalid. */ }
    return null;
  }
  let state = readState();
  function cleanUrl(url) {
    url.searchParams.delete('tour');
    url.searchParams.delete('tour-event');
    return url;
  }
  function persist() {
    let stored = false;
    try {sessionStorage.setItem(storageKey, JSON.stringify(state)); stored = true;} catch { /* Use URL state for this guided visit. */ }
    const url = cleanUrl(new URL(location.href));
    if (!stored && state.status === 'active') {
      url.searchParams.set('tour', String(state.step));
      if (state.eventUrl) url.searchParams.set('tour-event', state.eventUrl);
    }
    history.replaceState(history.state, '', url);
    return stored;
  }
  function pathForStep() {
    return steps[state.step].path || state.eventUrl || '/demo/';
  }
  function navigate() {
    const stored = persist();
    const destination = new URL(pathForStep(), location.origin);
    if (destination.pathname !== location.pathname || destination.search !== cleanUrl(new URL(location.href)).search) {
      if (!stored) {
        destination.searchParams.set('tour', String(state.step));
        if (state.eventUrl) destination.searchParams.set('tour-event', state.eventUrl);
      }
      location.assign(destination.href);
    } else render();
  }
  function move(delta) {
    next.disabled = back.disabled = true;
    state.step += delta;
    if (!state.eventUrl && state.step >= 6 && state.step <= 7) state.step = delta > 0 ? 8 : 5;
    navigate();
  }
  function finish(status) {
    renderId++;
    state.status = status;
    persist();
    dialog.close();
    document.documentElement.classList.remove('tour-open');
    target = null;
    if (opener?.isConnected) opener.focus({preventScroll:true});
    else {
      const main = document.querySelector('#main');
      main.setAttribute('tabindex','-1');
      main.focus({preventScroll:true});
    }
  }
  function completion() {
    const checks = [
      [dialog.dataset.sourcesReady === 'true', 'Fuentes argentinas cargadas', 'Fuentes pendientes'],
      [dialog.dataset.criteriaReady === 'true', 'Criterios editoriales activos', 'Criterios pendientes'],
      [dialog.dataset.newsReady === 'true', 'Noticias disponibles para explorar', 'Noticias pendientes de carga']
    ];
    const ready = checks.every(([available]) => available);
    heading.textContent = ready ? 'Ya está todo listo para explorar tu agenda' : 'Estamos preparando tu radar';
    copy.textContent = ready
      ? 'Esta demo ya tiene fuentes argentinas, criterios editoriales y noticias cargadas. Podés detectar temas relevantes, contrastar la cobertura y registrar decisiones.'
      : 'Terminaste el recorrido. Todavía falta completar la carga para explorar todas las señales. Podés revisar lo disponible y usar Cargar novedades para incorporar la próxima captura.';
    checklist.replaceChildren(...checks.map(([available, yes, no]) => {
      const item = document.createElement('li');
      item.className = available ? 'is-ready' : 'is-pending';
      item.textContent = `${available ? '✓' : '○'} ${available ? yes : no}`;
      return item;
    }));
    checklist.hidden = false;
    next.textContent = ready ? 'Empezar a explorar' : 'Ir al radar';
  }
  async function findTarget(name) {
    if (!name) return null;
    const selector = `[data-tour="${name}"]`;
    const current = document.querySelector(selector);
    if (current) return current;
    // Only editorial controls arrive asynchronously; empty datasets need no delay.
    if (name !== 'criteria') return null;
    return new Promise(resolve => {
      const observer = new MutationObserver(() => {
        const element = document.querySelector(selector);
        if (element) {clearTimeout(timer); observer.disconnect(); resolve(element);}
      });
      const timer = setTimeout(() => {observer.disconnect(); resolve(null);}, 3000);
      observer.observe(document.querySelector('#criteria-controls') || document.body, {childList:true, subtree:true});
    });
  }
  function place() {
    if (!dialog.open) return;
    const width = innerWidth, height = innerHeight, margin = 16, gap = 20;
    const cardWidth = card.offsetWidth, cardHeight = card.offsetHeight;
    const rect = target?.getBoundingClientRect();
    let x = (width - cardWidth) / 2, y = (height - cardHeight) / 2;
    let highlight = null;
    if (rect && rect.width && rect.height) {
      const bottomLimit = width < 760 ? height - cardHeight - 36 : height - margin;
      highlight = {
        left:Math.max(8, rect.left - 8), right:Math.min(width - 8, rect.right + 8),
        top:Math.max(8, rect.top - 8), bottom:Math.min(bottomLimit, rect.bottom + 8)
      };
      if (highlight.bottom <= highlight.top || highlight.right <= highlight.left) highlight = null;
    }
    if (highlight) {
      const h = highlight;
      if (width < 760) {x = margin; y = height - cardHeight - margin;}
      else if (width - h.right >= cardWidth + gap + margin) {x = h.right + gap; y = h.top;}
      else if (h.left >= cardWidth + gap + margin) {x = h.left - cardWidth - gap; y = h.top;}
      else if (height - h.bottom >= cardHeight + gap + margin) {y = h.bottom + gap;}
      else if (h.top >= cardHeight + gap + margin) {y = h.top - cardHeight - gap;}
      else {y = height - cardHeight - margin; h.bottom = Math.min(h.bottom, y - gap);}
      if (h.bottom <= h.top) highlight = null;
    }
    spotlight.hidden = !highlight;
    dialog.classList.toggle('has-target', !!highlight);
    if (highlight) {
      const h = highlight;
      Object.assign(spotlight.style, {left:`${h.left}px`, top:`${h.top}px`, width:`${h.right-h.left}px`, height:`${h.bottom-h.top}px`});
    }
    Object.assign(card.style, {
      left:`${Math.max(margin, Math.min(x, width-cardWidth-margin))}px`,
      top:`${Math.max(margin, Math.min(y, height-cardHeight-margin))}px`
    });
  }
  const schedulePlacement = () => {if (!dialog.open || frame) return; frame = requestAnimationFrame(() => {frame=0;place();});};
  function revealTarget() {
    if (!target) return;
    target.scrollIntoView({block:'start', behavior:'instant'});
    window.scrollBy({top:-32, behavior:'instant'});
  }
  async function render() {
    const id = ++renderId;
    const step = steps[state.step];
    const last = state.step === steps.length - 1;
    heading.textContent = step.title;
    copy.textContent = step.copy;
    note.hidden = true;
    checklist.hidden = true;
    back.hidden = state.step === 0;
    next.textContent = state.step === 0 ? 'Comenzar recorrido' : state.step === 7 ? 'Terminar recorrido' : 'Siguiente →';
    dialog.querySelector('#tour-step').textContent = state.step === 0 ? 'Tu primera visita' : last ? 'Recorrido completado' : `Paso ${state.step} de 7`;
    dialog.querySelector('.tour-progress span').style.width = `${state.step / 8 * 100}%`;
    dialog.dataset.step = String(state.step);
    dialog.querySelector('[data-tour-skip]').textContent = last ? 'Cerrar' : 'Omitir';
    dialog.querySelector('[data-tour-skip]').setAttribute('aria-label', last ? 'Cerrar tutorial' : 'Omitir tutorial');
    if (last) completion();
    target = await findTarget(step.target);
    if (id !== renderId || state.status !== 'active') return;
    if (state.step === 4) {
      state.eventUrl = eventUrl(document.querySelector('[data-tour="event-link"]')?.getAttribute('href'));
      persist();
    }
    if (step.target && !target) {
      note.textContent = state.step === 4
        ? 'Todavía no hay acontecimientos en el radar. Cuando lleguen noticias, vas a poder abrir su evidencia y registrar decisiones.'
        : 'Este control todavía no está disponible. Podés continuar el recorrido y volver desde Ver tutorial.';
      note.hidden = false;
    } else if (state.step === 5 && !state.eventUrl) {
      note.textContent = 'Cuando haya acontecimientos, también podrás revisar su evidencia y registrar decisiones. Por ahora vamos al cierre.';
      note.hidden = false;
    } else if (state.step === 0) {
      note.textContent = 'Son 7 pasos. Podés omitirlos y volver desde Ver tutorial cuando quieras.';
      note.hidden = false;
    }
    document.documentElement.classList.add('tour-open');
    if (target) {
      for (let ancestor = target.parentElement; ancestor; ancestor = ancestor.parentElement) {
        if (ancestor.matches('details')) ancestor.open = true;
      }
      revealTarget();
    }
    if (!dialog.open) dialog.showModal();
    heading.focus({preventScroll:true});
    next.disabled = back.disabled = false;
    place();
  }
  restartTour = button => {
    opener = button;
    state = initial();
    navigate();
  };
  next.addEventListener('click', () => state.step === steps.length - 1 ? finish('completed') : move(1));
  back.addEventListener('click', () => move(-1));
  dialog.querySelector('[data-tour-skip]').addEventListener('click', () => finish('skipped'));
  dialog.addEventListener('cancel', event => {event.preventDefault(); finish('skipped');});
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...dialog.querySelectorAll('button:not(:disabled)')].filter(button => !button.hidden);
    const index = controls.indexOf(document.activeElement);
    if (index < 0 || (!event.shiftKey && index === controls.length - 1) || (event.shiftKey && index === 0)) {
      event.preventDefault();
      controls[event.shiftKey ? controls.length - 1 : 0].focus();
    }
  });
  addEventListener('resize', () => {if(dialog.open) revealTarget(); place();});
  addEventListener('scroll', schedulePlacement, true);
  new ResizeObserver(schedulePlacement).observe(card);
  // Reconcile browser back/forward cache with the latest completion/skip state.
  addEventListener('pageshow', event => {
    if (!event.persisted) return;
    state = readState();
    if (state?.status === 'active') navigate();
    else {dialog.close(); document.documentElement.classList.remove('tour-open');}
  });
  if (state?.status === 'active') navigate();
})();
