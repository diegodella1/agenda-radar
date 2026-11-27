const helpDialog = document.querySelector('#editorial-help');
const helpSteps = [
  [window.RadarI18n.t('Detectar una señal'), window.RadarI18n.t('Elegí un período. Las tarjetas priorizan acontecimientos según tus fuentes y criterios editoriales; las barras comparan atención propia y de referencia.')],
  [window.RadarI18n.t('Entender y contrastar'), window.RadarI18n.t('Abrí Entender diferencia o una fila del gráfico. Contrastá medios, grupos independientes y publicaciones originales. Una brecha no demuestra que un tema esté escalando.')],
  [window.RadarI18n.t('Decidir y observar cambios'), window.RadarI18n.t('Desde Ver evidencia registrá Seguir, Revisar, Descartar o Aceptar y explicá el motivo. En demo, Cargar novedades agrega publicaciones reales y enlaza los acontecimientos afectados.')]
];
let helpStep = 0;
function renderHelp() {
  document.querySelector('#help-step').textContent = window.RadarI18n.t('Paso {step} de 3',{step:helpStep+1});
  document.querySelector('#help-title').textContent = helpSteps[helpStep][0];
  document.querySelector('#help-copy').textContent = helpSteps[helpStep][1];
  document.querySelector('[data-help-next]').textContent = helpStep === 2 ? window.RadarI18n.t('Terminar') : window.RadarI18n.t('Siguiente →');
}
export function openHelp() {helpStep=0;renderHelp();helpDialog.showModal();}
document.querySelector('[data-help-close]')?.addEventListener('click', () => helpDialog.close());
document.querySelector('[data-help-next]')?.addEventListener('click', () => {if(helpStep===2)helpDialog.close();else{helpStep++;renderHelp();}});
