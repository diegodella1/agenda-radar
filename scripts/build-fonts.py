"""Regenerate local WOFF2 files: uv run --with 'fonttools[woff]' scripts/build-fonts.py."""

import hashlib
import re
from pathlib import Path

from fontTools.ttLib import TTFont

static = Path(__file__).resolve().parents[1] / 'src/agenda_radar/static'
for source in sorted((static / 'fonts').glob('*.ttf')):
    font = TTFont(source, recalcTimestamp=False)
    font.flavor = 'woff2'
    target = source.with_suffix('.woff2')
    font.save(target)
    version = hashlib.sha256(target.read_bytes()).hexdigest()[:12]
    for stylesheet in (static / 'app.css', static / 'public.css'):
        content = re.sub(
            rf"fonts/{re.escape(target.name)}(?:\?v=[a-f0-9]+)?",
            f'fonts/{target.name}?v={version}',
            stylesheet.read_text(),
        )
        stylesheet.write_text(content)
    print(f'{source.name}: {source.stat().st_size} → {target.stat().st_size} bytes')
