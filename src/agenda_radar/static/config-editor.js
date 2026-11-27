'use strict';
(() => {
  const form = document.querySelector('[data-config]');
  if (!form) return;
  const json = form.elements.config;
  const original = JSON.parse(json.value);
  let draft = structuredClone(original), previewTimer, changeFrame;
  const pendingSections = new Map();
  const syncJson = () => {json.value = JSON.stringify(draft,null,2);};
  json.closest("details").addEventListener("toggle", event => {if(event.target.open)syncJson();});
  const sources = JSON.parse(document.querySelector('#criteria-sources').textContent);
  const host = document.querySelector('#criteria-controls');
  const state = document.querySelector('#criteria-state');
  const publish = document.querySelector('#criteria-publish');
  const resultPanel = document.querySelector('#preview-result');
  const same = (a,b) => JSON.stringify(a) === JSON.stringify(b);
  const node = (tag, text, cls) => {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  };
  function changed() {
    clearTimeout(previewTimer);
    publish.disabled = true;
    resultPanel.hidden = true;
    if(changeFrame)return;
    changeFrame=requestAnimationFrame(()=>{
      changeFrame=0;
      const count = Object.keys(original).filter(k => !same(original[k],draft[k])).length;
      state.textContent = count ? count + window.RadarI18n.t(' ajustes modificados · Compará antes de publicar.') : window.RadarI18n.t('Sin cambios pendientes.');
      if(json.closest('details').open)syncJson();
    });
  }
  function deferSection(box, build) {
    const mount=()=>{
      if(!pendingSections.has(box))return;
      pendingSections.delete(box);
      build();
    };
    pendingSections.set(box,mount);
    box.addEventListener('toggle',()=>{if(box.open)mount();});
  }
  function section(title, description, open=false) {
    const box = node('details',undefined,'panel criteria-section');box.open=open;
    box.append(node('summary',title),node('p',description,'muted'));
    host.append(box);return box;
  }
  function input(parent, title, help, type='text') {
    const label=node('label',title);
    const control=node('input');control.type=type;
    const id='criterion-'+(++input.count);control.id=id;
    const hint=node('small',help,'criteria-hint');hint.id=id+'-hint';
    control.setAttribute('aria-describedby',hint.id);
    label.append(control);parent.append(label,hint);return control;
  }
  input.count=0;
  function scalar(parent,key,title,help,min,max,step=1) {
    const box=node('div',undefined,'criteria-field');
    const control=input(box,title,help,typeof draft[key]==='number'?'number':'text');
    if(control.type==='number'){control.min=min;control.max=max;control.step=step;control.required=true;}
    control.value=draft[key] ?? '';
    control.dataset.criterion=key;
    control.addEventListener('input',()=>{
      if(!control.checkValidity()) {changed();return;}
      draft[key]=control.type==='number'?Number(control.value):control.value;changed();
    });
    parent.append(box);
  }
  function weight(parent,value,max,onChange,title) {
    const wrap=node('div',undefined,'criteria-weight');
    const range=node('input');range.type='range';range.min=0;range.max=max;range.step='any';range.value=value;
    range.setAttribute('aria-label',title+window.RadarI18n.t(' · deslizador'));
    const number=node('input');number.type='number';number.min=0;number.max=max;number.step='any';number.required=true;number.value=value;
    number.setAttribute('aria-label',title+window.RadarI18n.t(' · valor'));
    const meter=node('meter');meter.min=0;meter.max=max;meter.value=value;meter.setAttribute('aria-label',title);
    const caption=node('span',undefined,'criteria-weight-caption');
    function update(v){
      meter.value=v;
      caption.textContent=max===5 ? (v===1?window.RadarI18n.t('1× · Neutro'):v===0?window.RadarI18n.t('0× · Sin afinidad'):v+'× · '+(v<1?window.RadarI18n.t('Menor afinidad'):window.RadarI18n.t('Mayor afinidad'))) : v+'/100 · '+(v===0?window.RadarI18n.t('Sin contribución'):window.RadarI18n.t('Peso de referencia'));
      range.setAttribute('aria-valuetext',caption.textContent);
    }
    update(value);
    range.addEventListener('input',()=>{number.value=range.value;update(Number(range.value));onChange(Number(range.value));});
    number.addEventListener('input',()=>{if(number.checkValidity()){range.value=number.value;update(Number(number.value));onChange(Number(number.value));}else changed();});
    wrap.append(range,number,meter,caption);parent.append(wrap);
  }
  function dictionary(parent,key,title,help,max=5,options=null) {
    const box=node('section',undefined,'criteria-dictionary');
    box.append(node('h3',title),node('p',help,'muted'));
    const list=node('div');box.append(list);
    const rows = new Map();
    const sourceNames = new Map((options || []).map(source=>[String(source.id),source.name]));
    function render(){
      for(const [name,row] of rows)if(!Object.hasOwn(draft[key],name)){row.remove();rows.delete(name);}
      list.querySelector('.criteria-empty')?.remove();
      if(!Object.keys(draft[key]).length)list.append(node('p',window.RadarI18n.t('Sin ajustes específicos. Se usan los valores habituales.'),'criteria-empty'));
      for(const [name,value] of Object.entries(draft[key])){
        if(rows.has(name))continue;
        const row=node('div',undefined,'criteria-rule');
        const label=sourceNames.get(name) || (options?window.RadarI18n.t('Fuente #')+name:name);
        row.append(node('strong',label));
        weight(row,value,max,v=>{draft[key][name]=v;changed();},label);
        const remove=node('button',window.RadarI18n.t('Quitar ajuste'),'quiet');remove.type='button';
        remove.setAttribute('aria-label',window.RadarI18n.t('Quitar ajuste de ')+label);
        remove.addEventListener('click',()=>{delete draft[key][name];render();changed();add.focus();});
        row.append(remove);list.append(row);rows.set(name,row);
      }
    }
    const addLabel=node('label',options?window.RadarI18n.t('Fuente a ajustar'):window.RadarI18n.t('Nuevo ajuste'));
    const entry=node(options?'select':'input');
    entry.setAttribute('aria-label',window.RadarI18n.t('Agregar en ')+title);
    if(options){
      for(const source of options){const option=node('option',source.name+' · base '+source.weight);option.value=source.id;entry.append(option);}
    } else {entry.placeholder=key==='hourly_priorities'?window.RadarI18n.t('Hora: 0 a 23'):key==='geo_priorities'?window.RadarI18n.t('Código de país, ej. AR'):window.RadarI18n.t('Nombre, ej. ')+(key==='topic_priorities'?'economía':window.RadarI18n.t('Congreso'));}
    if(key==='topic_priorities'){
      const suggestions=node('datalist');suggestions.id='criteria-topic-names';
      for(const name of Object.keys(draft.topic_keywords))suggestions.append(node('option',name));
      entry.setAttribute('list',suggestions.id);box.append(suggestions);
    }
    addLabel.append(entry);
    const add=node('button',window.RadarI18n.t('Agregar ajuste'),'secondary');add.type='button';if(options&&!options.length)add.disabled=true;
    add.addEventListener('click',()=>{
      const name=entry.value.trim();entry.setCustomValidity('');
      if(!name || Object.hasOwn(draft[key],name))entry.setCustomValidity(window.RadarI18n.t('Ingresá un nombre nuevo, sin repetir.'));
      if(key==='hourly_priorities'&&!/^(0|[1-9]|1[0-9]|2[0-3])$/.test(name))entry.setCustomValidity(window.RadarI18n.t('Usá una hora entera entre 0 y 23.'));
      if(!entry.reportValidity())return;
      Object.defineProperty(draft[key],name,{value:options?Number(options.find(s=>String(s.id)===name).weight):1,writable:true,enumerable:true,configurable:true});
      render();changed();if(!options)entry.value='';list.querySelector('.criteria-rule:last-child input')?.focus();
    });
    entry.addEventListener('input',()=>entry.setCustomValidity(''));
    const actions=node('div',undefined,'criteria-add');actions.append(addLabel,add);box.append(actions);parent.append(box);render();
  }
  function terms(parent,key,title,help) {
    const label=node('label',title), area=node('textarea');area.rows=3;area.value=draft[key].join('\n');
    area.dataset.criterion=key;
    const hint=node('small',help+window.RadarI18n.t(' Un término por línea.'),'criteria-hint');
    label.append(area,hint);parent.append(label);
    area.addEventListener('input',()=>{draft[key]=area.value.split('\n').map(s=>s.trim()).filter(Boolean);changed();});
  }
  function topics(parent){
    const box=node('section',undefined,'criteria-dictionary');box.append(node('h3',window.RadarI18n.t('Palabras clave por tema')),node('p',window.RadarI18n.t('Se usan para clasificar nuevas publicaciones. Editarlas no reclasifica el historial.'),'muted'));
    const list=node('div');box.append(list);
    const rows = new Map();
    function render(){
      for(const [topic,row] of rows)if(!Object.hasOwn(draft.topic_keywords,topic)){row.remove();rows.delete(topic);}
      for(const [topic,keywords] of Object.entries(draft.topic_keywords)){
        if(rows.has(topic))continue;
        const row=node('div',undefined,'criteria-topic');
        const label=node('label',topic),area=node('textarea');area.rows=2;area.value=keywords.join(', ');
        area.setAttribute('aria-label',window.RadarI18n.t('Palabras clave de ')+topic);
        area.addEventListener('input',()=>{draft.topic_keywords[topic]=area.value.split(',').map(s=>s.trim()).filter(Boolean);changed();});
        label.append(area,node('small',window.RadarI18n.t('Separá las palabras con comas.'),'criteria-hint'));
        const remove=node('button',window.RadarI18n.t('Quitar tema'),'quiet');remove.type='button';
        remove.setAttribute('aria-label',window.RadarI18n.t('Quitar palabras clave de ')+topic);
        remove.addEventListener('click',()=>{delete draft.topic_keywords[topic];render();changed();entry.focus();});
        row.append(label,remove);list.append(row);rows.set(topic,row);
      }
    }
    const entry=input(box,window.RadarI18n.t('Nuevo tema'),window.RadarI18n.t('Ej.: ambiente, deportes o comunidad.'));
    const add=node('button',window.RadarI18n.t('Agregar tema'),'secondary');add.type='button';
    entry.addEventListener('input',()=>entry.setCustomValidity(''));
    add.addEventListener('click',()=>{
      const value=entry.value.trim();entry.setCustomValidity(!value||Object.hasOwn(draft.topic_keywords,value)?window.RadarI18n.t('Ingresá un tema nuevo, sin repetir.'):'');
      if(!entry.reportValidity())return;
      Object.defineProperty(draft.topic_keywords,value,{value:[],writable:true,enumerable:true,configurable:true});entry.value='';render();changed();list.querySelector('.criteria-topic:last-child textarea').focus();
    });box.append(add);parent.append(box);render();
  }
  function toggle(parent,key,title,help) {
    const label=node('label',undefined,'criteria-toggle');
    const check=node('input');check.type='checkbox';check.checked=draft[key];check.dataset.criterion=key;
    check.addEventListener('change',()=>{draft[key]=check.checked;changed();});
    label.append(check,node('span',title));parent.append(label,node('p',help,'criteria-hint'));
  }
  function render(){
    pendingSections.clear();
    host.replaceChildren();
    const editorial=section(window.RadarI18n.t('01 · Enfoque editorial'),window.RadarI18n.t('Dale más o menos afinidad a cada tema. 1× es neutro; los multiplicadores se combinan entre sí.'),true);
    dictionary(editorial,'topic_priorities',window.RadarI18n.t('Prioridad por tema'),window.RadarI18n.t('Usá el nombre del tema tal como aparece en los acontecimientos.'));
    (editorial.querySelector('.criteria-rule') || editorial.querySelector('summary')).dataset.tour='criteria';
    topics(editorial);
    const sourcesBox=section(window.RadarI18n.t('02 · Peso de las fuentes'),window.RadarI18n.t('Ajustá cuánto contribuye cada fuente de referencia. Quitar el ajuste recupera el peso configurado en Fuentes.'));
    deferSection(sourcesBox,()=>{
      dictionary(sourcesBox,'source_weights',window.RadarI18n.t('Fuentes de referencia'),window.RadarI18n.t('Escala de 0 a 100, independiente por fuente. El cálculo agrupa medios del mismo grupo editorial.'),100,sources.filter(s=>s.scope==='reference'));
    });
    const contextual=section(window.RadarI18n.t('03 · Personas, lugares y horarios'),window.RadarI18n.t('Afiná tu criterio sin cambiar la fórmula de prioridad.'));
    deferSection(contextual,()=>{
      dictionary(contextual,'entity_priorities',window.RadarI18n.t('Personas u organizaciones'),window.RadarI18n.t('Coincidencia de texto en el título del acontecimiento, sin distinguir mayúsculas.'));
      dictionary(contextual,'geo_priorities',window.RadarI18n.t('Países de las fuentes'),window.RadarI18n.t('Se utiliza el mayor multiplicador entre los países de las fuentes participantes; no es la ubicación del acontecimiento.'));
      dictionary(contextual,'hourly_priorities',window.RadarI18n.t('Hora del análisis'),window.RadarI18n.t('Se aplica según la hora actual del análisis, no la hora de publicación.'));
      scalar(contextual,'timezone',window.RadarI18n.t('Zona horaria'),window.RadarI18n.t('Usá una zona IANA, por ejemplo America/Argentina/Buenos_Aires.'));
    });
    const alerts=section(window.RadarI18n.t('04 · Cuándo avisarme'),window.RadarI18n.t('Umbrales más exigentes reducen las señales elegibles. La comparación inferior muestra prioridades y brechas; no simula envíos.'));
    deferSection(alerts,()=>{
      const grid=node('div',undefined,'form-grid');alerts.append(grid);
      for(const args of [
        ['minimum_gap_pp',window.RadarI18n.t('Brecha mínima · pp'),window.RadarI18n.t('Diferencia referencia − propia para la regla de brecha.'),0,100,0.1],
        ['minimum_independent_sources',window.RadarI18n.t('Grupos independientes mínimos'),window.RadarI18n.t('Grupos editoriales, no cantidad de artículos.'),2,50,1],
        ['minimum_confidence',window.RadarI18n.t('Confianza mínima · 0 a 1'),window.RadarI18n.t('Calidad de agrupamiento y disponibilidad. No mide veracidad.'),0,1,0.01],
        ['cooldown_minutes',window.RadarI18n.t('Espera entre alertas · minutos'),window.RadarI18n.t('Evita repetir una alerta demasiado pronto.'),20,10080,1],
        ['priority_threshold',window.RadarI18n.t('Prioridad alta · 0 a 1'),window.RadarI18n.t('Umbral para alertas de prioridad sin cobertura.'),0,1,0.01],
        ['emerging_velocity',window.RadarI18n.t('Velocidad emergente'),window.RadarI18n.t('1 equivale a un aumento del 100% de grupos: últimas 2 h frente a las 2 h anteriores.'),0,100,0.1],
        ['agenda_shift_pp',window.RadarI18n.t('Cambio de agenda · pp'),window.RadarI18n.t('Variación mínima para detectar un cambio de agenda.'),1,100,0.1],
        ['high_impact_new_documents',window.RadarI18n.t('Publicaciones nuevas para alto impacto'),window.RadarI18n.t('Cantidad mínima de documentos nuevos.'),2,100,1],
        ['rearm_change_pp',window.RadarI18n.t('Cambio para repetir aviso · pp'),window.RadarI18n.t('Variación necesaria para volver a alertar.'),0,100,0.1],
        ['quiet_start',window.RadarI18n.t('Silencio desde · hora'),window.RadarI18n.t('Hora de inicio, en la zona horaria configurada.'),0,23,1],
        ['quiet_end',window.RadarI18n.t('Silencio hasta · hora'),window.RadarI18n.t('Hora de fin. Inicio y fin iguales desactivan el silencio.'),0,23,1]
      ])scalar(grid,...args);
      const rules=node('fieldset');rules.append(node('legend',window.RadarI18n.t('Reglas activas')));
      for(const [key,title] of Object.entries({editorial_gap:window.RadarI18n.t('Brecha de cobertura'),emerging_event:window.RadarI18n.t('Acontecimiento emergente'),priority_without_coverage:window.RadarI18n.t('Prioridad sin cobertura'),agenda_shift:window.RadarI18n.t('Cambio de agenda'),high_impact_update:window.RadarI18n.t('Actualización de alto impacto'),source_health_failure:window.RadarI18n.t('Problemas con fuentes')})){
        const label=node('label',undefined,'criteria-toggle'),check=node('input');check.type='checkbox';check.checked=draft.enabled_alert_rules.includes(key);
        check.addEventListener('change',()=>{draft.enabled_alert_rules=check.checked?[...draft.enabled_alert_rules,key]:draft.enabled_alert_rules.filter(x=>x!==key);changed();});
        label.append(check,node('span',title));rules.append(label);
      }alerts.append(rules);
    });
    const exclusions=section(window.RadarI18n.t('05 · Excepciones y tono'),window.RadarI18n.t('Definí qué debe perder prioridad y qué requiere una revisión humana.'));
    deferSection(exclusions,()=>{
      terms(exclusions,'excluded_terms',window.RadarI18n.t('Quitar prioridad cuando el título contenga'),window.RadarI18n.t('La prioridad queda en cero; el acontecimiento sigue disponible.'));
      terms(exclusions,'review_terms',window.RadarI18n.t('Marcar para revisión cuando el título contenga'),window.RadarI18n.t('Añade una señal de revisión.'));
      scalar(exclusions,'editorial_tone',window.RadarI18n.t('Tono editorial'),window.RadarI18n.t('Orientación de redacción; no cambia los pesos.'));
    });
    if(form.dataset.global==='true'){
      const global=section(window.RadarI18n.t('06 · Automatización y consumo'),window.RadarI18n.t('Ajustes globales del equipo. Activar una integración requiere credenciales y fuentes configuradas.'));
      deferSection(global,()=>{
        for(const args of [['run_enabled',window.RadarI18n.t('Monitoreo activo'),window.RadarI18n.t('Habilita el ciclo de monitoreo.')],['ai_enabled',window.RadarI18n.t('Asistente con IA'),window.RadarI18n.t('Permite el uso de IA con los límites definidos.')],['extraction_enabled',window.RadarI18n.t('Extracción con IA'),window.RadarI18n.t('Permite análisis de nuevas publicaciones con el modelo de extracción.')],['telegram_enabled',window.RadarI18n.t('Notificaciones por Telegram'),window.RadarI18n.t('Habilita notificaciones a cuentas vinculadas.')]])toggle(global,...args);
        for(const args of [
          ['ai_model',window.RadarI18n.t('Modelo del asistente'),window.RadarI18n.t('Identificador del modelo configurado.')],
          ['extraction_model',window.RadarI18n.t('Modelo de extracción'),window.RadarI18n.t('Identificador del modelo para extraer información.')],
          ['daily_budget_usd',window.RadarI18n.t('Presupuesto diario · USD'),window.RadarI18n.t('Límite de consumo estimado.'),0,10000,0.01],
          ['monthly_budget_usd',window.RadarI18n.t('Presupuesto mensual · USD'),window.RadarI18n.t('Límite de consumo estimado.'),0,100000,0.01],
          ['ai_input_usd_million',window.RadarI18n.t('Asistente: entrada · USD/millón de tokens'),window.RadarI18n.t('Tarifa usada para estimar consumo.'),0,1000000,0.001],
          ['ai_output_usd_million',window.RadarI18n.t('Asistente: salida · USD/millón de tokens'),window.RadarI18n.t('Tarifa usada para estimar consumo.'),0,1000000,0.001],
          ['extraction_input_usd_million',window.RadarI18n.t('Extracción: entrada · USD/millón de tokens'),window.RadarI18n.t('Tarifa usada para estimar consumo.'),0,1000000,0.001],
          ['extraction_output_usd_million',window.RadarI18n.t('Extracción: salida · USD/millón de tokens'),window.RadarI18n.t('Tarifa usada para estimar consumo.'),0,1000000,0.001]
        ])scalar(global,...args);
      });
    }
  }
  function validate(){
    for(const mount of [...pendingSections.values()])mount();
    syncJson();
    for(const control of form.querySelectorAll('input,select,textarea')){
      if(control.name==='reason')continue;
      if(!control.checkValidity()){
        for(let parent=control.parentElement;parent&&parent!==form;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true;
        control.reportValidity();return false;
      }
    }return true;
  }
  function preview(result,snapshot){
    if(!same(snapshot,draft)){state.textContent=window.RadarI18n.t('El borrador cambió mientras se calculaba. Volvé a comparar.');return;}
    resultPanel.replaceChildren();
    resultPanel.append(node('h2',window.RadarI18n.t('Así cambia tu radar · últimas 24 h')));
    const before=new Map(result.before.rows.map(row=>[row.event_id,row]));
    const rows=result.after.rows;
    const changedCount=rows.filter(row=>!same([row.priority,row.gap_pp],[before.get(row.event_id)?.priority,before.get(row.event_id)?.gap_pp])).length;
    resultPanel.append(node('p',rows.length ? changedCount+window.RadarI18n.t(' de ')+rows.length+window.RadarI18n.t(' acontecimientos cambian su prioridad o brecha. Escala de prioridad: 0–100.') : window.RadarI18n.t('Sin acontecimientos para comparar en las últimas 24 horas.')));
    resultPanel.append(node('p',window.RadarI18n.t('No predice alertas ni reclasifica publicaciones existentes. Los umbrales y palabras clave pueden guardarse aunque aquí no cambien los resultados.'),'muted'));
    const more=node('details');more.append(node('summary',window.RadarI18n.t('Ver otros acontecimientos (')+Math.max(0,rows.length-6)+')'));
    for(const [index,row] of rows.entries()){
      const previous=before.get(row.event_id);
      const card=node('article',undefined,'criteria-preview-row');
      const link=node('a',row.label);link.href=appUrl('/events/'+row.event_id+'?window=24h');link.target='_blank';link.rel='noopener';card.append(link);
      for(const [label,value] of [[window.RadarI18n.t('Activa'),previous?.priority],[window.RadarI18n.t('Borrador'),row.priority]]){
        const bar=node('div',undefined,'criteria-comparison');bar.append(node('span',label));
        const meter=node('meter');meter.min=0;meter.max=100;meter.value=value==null?0:value*100;meter.setAttribute('aria-label',label+window.RadarI18n.t(' · prioridad'));
        if(value!=null)bar.append(meter);
        bar.append(node('strong',value==null?window.RadarI18n.t('Sin datos'):(value*100).toFixed(1)));card.append(bar);
      }
      const pp=value=>value==null?window.RadarI18n.t('Sin datos'):value.toFixed(1)+' pp';
      card.append(node('small',window.RadarI18n.t('Brecha: ')+pp(previous?.gap_pp)+' → '+pp(row.gap_pp)));(index<6?resultPanel:more).append(card);
    }
    if(rows.length>6)resultPanel.append(more);
    resultPanel.hidden=false;publish.disabled=false;
    state.textContent=window.RadarI18n.t('Comparación lista · Revisá el efecto y escribí el motivo para publicar.');
    resultPanel.focus();
    previewTimer=setTimeout(()=>{publish.disabled=true;state.textContent=window.RadarI18n.t('La comparación venció. Volvé a comparar antes de publicar.');},30*60*1000);
  }
  document.querySelector('#criteria-reset').addEventListener('click',()=>{
    draft=structuredClone(original);render();changed();form.elements.reason.value='';
  });
  window.configEditor={read:()=>{syncJson();return structuredClone(draft);},validate,preview};
  render();
  host.classList.remove('criteria-loading');
  host.setAttribute('aria-busy','false');
})();
