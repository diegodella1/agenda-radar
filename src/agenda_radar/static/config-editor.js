'use strict';
(() => {
  const form = document.querySelector('[data-config]');
  if (!form) return;
  const json = form.elements.config;
  const original = JSON.parse(json.value);
  let draft = structuredClone(original), previewTimer;
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
    json.value = JSON.stringify(draft,null,2);
    clearTimeout(previewTimer);
    publish.disabled = true;
    const count = Object.keys(original).filter(k => !same(original[k],draft[k])).length;
    state.textContent = count ? count + ' ajustes modificados · Compará antes de publicar.' : 'Sin cambios pendientes.';
    resultPanel.hidden = true;
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
    range.setAttribute('aria-label',title+' · deslizador');
    const number=node('input');number.type='number';number.min=0;number.max=max;number.step='any';number.required=true;number.value=value;
    number.setAttribute('aria-label',title+' · valor');
    const meter=node('meter');meter.min=0;meter.max=max;meter.value=value;meter.setAttribute('aria-label',title);
    const caption=node('span',undefined,'criteria-weight-caption');
    function update(v){
      meter.value=v;
      caption.textContent=max===5 ? (v===1?'1× · Neutro':v===0?'0× · Sin afinidad':v+'× · '+(v<1?'Menor afinidad':'Mayor afinidad')) : v+'/100 · '+(v===0?'Sin contribución':'Peso de referencia');
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
    function render(){
      list.replaceChildren();
      if(!Object.keys(draft[key]).length)list.append(node('p','Sin ajustes específicos. Se usan los valores habituales.','criteria-empty'));
      for(const [name,value] of Object.entries(draft[key])){
        const row=node('div',undefined,'criteria-rule');
        const source=options?.find(s=>String(s.id)===name);
        const label=source?source.name:options?'Fuente #'+name:name;
        row.append(node('strong',label));
        weight(row,value,max,v=>{draft[key][name]=v;changed();},label);
        const remove=node('button','Quitar ajuste','quiet');remove.type='button';
        remove.setAttribute('aria-label','Quitar ajuste de '+label);
        remove.addEventListener('click',()=>{delete draft[key][name];render();changed();add.focus();});
        row.append(remove);list.append(row);
      }
    }
    const addLabel=node('label',options?'Fuente a ajustar':'Nuevo ajuste');
    const entry=node(options?'select':'input');
    entry.setAttribute('aria-label','Agregar en '+title);
    if(options){
      for(const source of options){const option=node('option',source.name+' · base '+source.weight);option.value=source.id;entry.append(option);}
    } else {entry.placeholder=key==='hourly_priorities'?'Hora: 0 a 23':key==='geo_priorities'?'Código de país, ej. AR':'Nombre, ej. '+(key==='topic_priorities'?'economía':'Congreso');}
    if(key==='topic_priorities'){
      const suggestions=node('datalist');suggestions.id='criteria-topic-names';
      for(const name of Object.keys(draft.topic_keywords))suggestions.append(node('option',name));
      entry.setAttribute('list',suggestions.id);box.append(suggestions);
    }
    addLabel.append(entry);
    const add=node('button','Agregar ajuste','secondary');add.type='button';if(options&&!options.length)add.disabled=true;
    add.addEventListener('click',()=>{
      const name=entry.value.trim();entry.setCustomValidity('');
      if(!name || Object.hasOwn(draft[key],name))entry.setCustomValidity('Ingresá un nombre nuevo, sin repetir.');
      if(key==='hourly_priorities'&&!/^(0|[1-9]|1[0-9]|2[0-3])$/.test(name))entry.setCustomValidity('Usá una hora entera entre 0 y 23.');
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
    const hint=node('small',help+' Un término por línea.','criteria-hint');
    label.append(area,hint);parent.append(label);
    area.addEventListener('input',()=>{draft[key]=area.value.split('\n').map(s=>s.trim()).filter(Boolean);changed();});
  }
  function topics(parent){
    const box=node('section',undefined,'criteria-dictionary');box.append(node('h3','Palabras clave por tema'),node('p','Se usan para clasificar nuevas publicaciones. Editarlas no reclasifica el historial.','muted'));
    const list=node('div');box.append(list);
    function render(){
      list.replaceChildren();
      for(const [topic,keywords] of Object.entries(draft.topic_keywords)){
        const row=node('div',undefined,'criteria-topic');
        const label=node('label',topic),area=node('textarea');area.rows=2;area.value=keywords.join(', ');
        area.setAttribute('aria-label','Palabras clave de '+topic);
        area.addEventListener('input',()=>{draft.topic_keywords[topic]=area.value.split(',').map(s=>s.trim()).filter(Boolean);changed();});
        label.append(area,node('small','Separá las palabras con comas.','criteria-hint'));
        const remove=node('button','Quitar tema','quiet');remove.type='button';
        remove.setAttribute('aria-label','Quitar palabras clave de '+topic);
        remove.addEventListener('click',()=>{delete draft.topic_keywords[topic];render();changed();entry.focus();});
        row.append(label,remove);list.append(row);
      }
    }
    const entry=input(box,'Nuevo tema','Ej.: ambiente, deportes o comunidad.');
    const add=node('button','Agregar tema','secondary');add.type='button';
    entry.addEventListener('input',()=>entry.setCustomValidity(''));
    add.addEventListener('click',()=>{
      const value=entry.value.trim();entry.setCustomValidity(!value||Object.hasOwn(draft.topic_keywords,value)?'Ingresá un tema nuevo, sin repetir.':'');
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
    host.replaceChildren();
    const editorial=section('01 · Enfoque editorial','Dale más o menos afinidad a cada tema. 1× es neutro; los multiplicadores se combinan entre sí.',true);
    dictionary(editorial,'topic_priorities','Prioridad por tema','Usá el nombre del tema tal como aparece en los acontecimientos.');
    topics(editorial);
    const sourcesBox=section('02 · Peso de las fuentes','Ajustá cuánto contribuye cada fuente de referencia. Quitar el ajuste recupera el peso configurado en Fuentes.');
    dictionary(sourcesBox,'source_weights','Fuentes de referencia','Escala de 0 a 100, independiente por fuente. El cálculo agrupa medios del mismo grupo editorial.',100,sources.filter(s=>s.scope==='reference'));
    const contextual=section('03 · Personas, lugares y horarios','Afiná tu criterio sin cambiar la fórmula de prioridad.');
    dictionary(contextual,'entity_priorities','Personas u organizaciones','Coincidencia de texto en el título del acontecimiento, sin distinguir mayúsculas.');
    dictionary(contextual,'geo_priorities','Países de las fuentes','Se utiliza el mayor multiplicador entre los países de las fuentes participantes; no es la ubicación del acontecimiento.');
    dictionary(contextual,'hourly_priorities','Hora del análisis','Se aplica según la hora actual del análisis, no la hora de publicación.');
    scalar(contextual,'timezone','Zona horaria','Usá una zona IANA, por ejemplo America/Argentina/Buenos_Aires.');
    const alerts=section('04 · Cuándo avisarme','Umbrales más exigentes reducen las señales elegibles. La comparación inferior muestra prioridades y brechas; no simula envíos.');
    const grid=node('div',undefined,'form-grid');alerts.append(grid);
    for(const args of [
      ['minimum_gap_pp','Brecha mínima · pp','Diferencia referencia − propia para la regla de brecha.',0,100,0.1],
      ['minimum_independent_sources','Grupos independientes mínimos','Grupos editoriales, no cantidad de artículos.',2,50,1],
      ['minimum_confidence','Confianza mínima · 0 a 1','Calidad de agrupamiento y disponibilidad. No mide veracidad.',0,1,0.01],
      ['cooldown_minutes','Espera entre alertas · minutos','Evita repetir una alerta demasiado pronto.',20,10080,1],
      ['priority_threshold','Prioridad alta · 0 a 1','Umbral para alertas de prioridad sin cobertura.',0,1,0.01],
      ['emerging_velocity','Velocidad emergente','1 equivale a un aumento del 100% de grupos: últimas 2 h frente a las 2 h anteriores.',0,100,0.1],
      ['agenda_shift_pp','Cambio de agenda · pp','Variación mínima para detectar un cambio de agenda.',1,100,0.1],
      ['high_impact_new_documents','Publicaciones nuevas para alto impacto','Cantidad mínima de documentos nuevos.',2,100,1],
      ['rearm_change_pp','Cambio para repetir aviso · pp','Variación necesaria para volver a alertar.',0,100,0.1],
      ['quiet_start','Silencio desde · hora','Hora de inicio, en la zona horaria configurada.',0,23,1],
      ['quiet_end','Silencio hasta · hora','Hora de fin. Inicio y fin iguales desactivan el silencio.',0,23,1]
    ])scalar(grid,...args);
    const rules=node('fieldset');rules.append(node('legend','Reglas activas'));
    for(const [key,title] of Object.entries({editorial_gap:'Brecha de cobertura',emerging_event:'Acontecimiento emergente',priority_without_coverage:'Prioridad sin cobertura',agenda_shift:'Cambio de agenda',high_impact_update:'Actualización de alto impacto',source_health_failure:'Problemas con fuentes'})){
      const label=node('label',undefined,'criteria-toggle'),check=node('input');check.type='checkbox';check.checked=draft.enabled_alert_rules.includes(key);
      check.addEventListener('change',()=>{draft.enabled_alert_rules=check.checked?[...draft.enabled_alert_rules,key]:draft.enabled_alert_rules.filter(x=>x!==key);changed();});
      label.append(check,node('span',title));rules.append(label);
    }alerts.append(rules);
    const exclusions=section('05 · Excepciones y tono','Definí qué debe perder prioridad y qué requiere una revisión humana.');
    terms(exclusions,'excluded_terms','Quitar prioridad cuando el título contenga','La prioridad queda en cero; el acontecimiento sigue disponible.');
    terms(exclusions,'review_terms','Marcar para revisión cuando el título contenga','Añade una señal de revisión.');
    scalar(exclusions,'editorial_tone','Tono editorial','Orientación de redacción; no cambia los pesos.');
    if(form.dataset.global==='true'){
      const global=section('06 · Automatización y consumo','Ajustes globales del equipo. Activar una integración requiere credenciales y fuentes configuradas.');
      for(const args of [['run_enabled','Monitoreo activo','Habilita el ciclo de monitoreo.'],['ai_enabled','Asistente con IA','Permite el uso de IA con los límites definidos.'],['extraction_enabled','Extracción con IA','Permite análisis de nuevas publicaciones con el modelo de extracción.'],['telegram_enabled','Notificaciones por Telegram','Habilita notificaciones a cuentas vinculadas.']])toggle(global,...args);
      for(const args of [
        ['ai_model','Modelo del asistente','Identificador del modelo configurado.'],
        ['extraction_model','Modelo de extracción','Identificador del modelo para extraer información.'],
        ['daily_budget_usd','Presupuesto diario · USD','Límite de consumo estimado.',0,10000,0.01],
        ['monthly_budget_usd','Presupuesto mensual · USD','Límite de consumo estimado.',0,100000,0.01],
        ['ai_input_usd_million','Asistente: entrada · USD/millón de tokens','Tarifa usada para estimar consumo.',0,1000000,0.001],
        ['ai_output_usd_million','Asistente: salida · USD/millón de tokens','Tarifa usada para estimar consumo.',0,1000000,0.001],
        ['extraction_input_usd_million','Extracción: entrada · USD/millón de tokens','Tarifa usada para estimar consumo.',0,1000000,0.001],
        ['extraction_output_usd_million','Extracción: salida · USD/millón de tokens','Tarifa usada para estimar consumo.',0,1000000,0.001]
      ])scalar(global,...args);
    }
  }
  function validate(){
    for(const control of form.querySelectorAll('input,select,textarea')){
      if(control.name==='reason')continue;
      if(!control.checkValidity()){
        for(let parent=control.parentElement;parent&&parent!==form;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true;
        control.reportValidity();return false;
      }
    }return true;
  }
  function preview(result,snapshot){
    if(!same(snapshot,draft)){state.textContent='El borrador cambió mientras se calculaba. Volvé a comparar.';return;}
    resultPanel.replaceChildren();
    resultPanel.append(node('h2','Así cambia tu radar · últimas 24 h'));
    const before=new Map(result.before.rows.map(row=>[row.event_id,row]));
    const rows=result.after.rows;
    const changedCount=rows.filter(row=>!same([row.priority,row.gap_pp],[before.get(row.event_id)?.priority,before.get(row.event_id)?.gap_pp])).length;
    resultPanel.append(node('p',rows.length ? changedCount+' de '+rows.length+' acontecimientos cambian su prioridad o brecha. Escala de prioridad: 0–100.' : 'Sin acontecimientos para comparar en las últimas 24 horas.'));
    resultPanel.append(node('p','No predice alertas ni reclasifica publicaciones existentes. Los umbrales y palabras clave pueden guardarse aunque aquí no cambien los resultados.','muted'));
    const more=node('details');more.append(node('summary','Ver otros acontecimientos ('+Math.max(0,rows.length-6)+')'));
    for(const [index,row] of rows.entries()){
      const previous=before.get(row.event_id);
      const card=node('article',undefined,'criteria-preview-row');
      const link=node('a',row.label);link.href=appUrl('/events/'+row.event_id+'?window=24h');link.target='_blank';link.rel='noopener';card.append(link);
      for(const [label,value] of [['Activa',previous?.priority],['Borrador',row.priority]]){
        const bar=node('div',undefined,'criteria-comparison');bar.append(node('span',label));
        const meter=node('meter');meter.min=0;meter.max=100;meter.value=value==null?0:value*100;meter.setAttribute('aria-label',label+' · prioridad');
        if(value!=null)bar.append(meter);
        bar.append(node('strong',value==null?'Sin datos':(value*100).toFixed(1)));card.append(bar);
      }
      const pp=value=>value==null?'Sin datos':value.toFixed(1)+' pp';
      card.append(node('small','Brecha: '+pp(previous?.gap_pp)+' → '+pp(row.gap_pp)));(index<6?resultPanel:more).append(card);
    }
    if(rows.length>6)resultPanel.append(more);
    resultPanel.hidden=false;publish.disabled=false;
    state.textContent='Comparación lista · Revisá el efecto y escribí el motivo para publicar.';
    resultPanel.focus();
    previewTimer=setTimeout(()=>{publish.disabled=true;state.textContent='La comparación venció. Volvé a comparar antes de publicar.';},30*60*1000);
  }
  document.querySelector('#criteria-reset').addEventListener('click',()=>{
    draft=structuredClone(original);render();changed();form.elements.reason.value='';
  });
  window.configEditor={read:()=>structuredClone(draft),validate,preview};
  render();
})();
