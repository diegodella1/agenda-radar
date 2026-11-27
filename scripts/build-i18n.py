"""Build the browser translation catalog from the shared, reviewed JSON catalog."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'src' / 'agenda_radar' / 'static'
catalog = json.loads((root / 'translations.json').read_text())
script = ''''use strict';
(() => {
  const catalog = CATALOG;
  const t = (message, values = {}) => {
    let output = document.documentElement.lang.startsWith('es') ? message : (catalog[message] ?? message);
    for (const [key, value] of Object.entries(values)) output = output.replaceAll('{' + key + '}', String(value));
    return output;
  };
  window.RadarI18n = {t};
  document.addEventListener('change', event => {
    if (!event.target.matches('[data-language]')) return;
    const url = new URL(location.href);
    url.searchParams.set('lang', event.target.value);
    location.assign(url.href);
  });
})();
'''
(root / 'i18n.js').write_text(script.replace('CATALOG', json.dumps(catalog, ensure_ascii=False)))
