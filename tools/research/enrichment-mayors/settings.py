"""Portable paths and bounded acquisition settings; no data is read on import."""
import datetime
import os
from pathlib import Path
import ssl
import tempfile

PACKAGE_DIR = Path(__file__).resolve().parent
WORK_DIR = Path(os.environ.get('MAYORS_WORK_DIR', str(Path(tempfile.gettempdir()) / 'localpoliticians-mayors')))
def path(name, default):
    return Path(os.environ.get(name, str(default))).expanduser()
def paths(name, defaults):
    value = os.environ.get(name)
    return [Path(p).expanduser() for p in value.split(os.pathsep) if p] if value is not None else list(defaults)

INPUT = path('MAYORS_INPUT', WORK_DIR / 'mayors.json')
COLLECTED = path('MAYORS_COLLECTED', WORK_DIR / 'collected.json')
AUDITED = path('MAYORS_AUDITED', WORK_DIR / 'audited.json')
OUTPUT = path('MAYORS_OUTPUT', WORK_DIR / 'enriched-mayors.json')
CACHE = path('MAYORS_CACHE', WORK_DIR / 'cache')
CHECKPOINT = path('MAYORS_CHECKPOINT', WORK_DIR / 'checkpoint.jsonl')
REPORT = path('MAYORS_REPORT', WORK_DIR / 'quality-report.json')
SUPPLEMENTS = paths('MAYORS_SUPPLEMENTS', [PACKAGE_DIR / 'reviewed-supplements.json'])
CHECKED_AT = os.environ.get('MAYORS_CHECKED_AT', datetime.date.today().isoformat())
datetime.date.fromisoformat(CHECKED_AT)
PARALLEL = int(os.environ.get('MAYORS_PARALLEL', '12'))
MAX_PAGES = int(os.environ.get('MAYORS_MAX_PAGES', '4'))
EXPECTED_COUNT = int(os.environ.get('MAYORS_EXPECTED_COUNT', '1741'))
if not 1 <= PARALLEL <= 12 or not 1 <= MAX_PAGES <= 8:
    raise ValueError('MAYORS_PARALLEL must be 1–12; MAYORS_MAX_PAGES must be 1–8')
SSL_CONTEXT = ssl.create_default_context(cafile=os.environ.get('MAYORS_CA_BUNDLE'))

def write_json(target, data):
    import json
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
