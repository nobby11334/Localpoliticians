"""Portable paths/settings for the research scripts (no network or data I/O on import)."""
import os
from datetime import date
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent

def env_path(name, default):
    return Path(os.environ.get(name, str(default))).expanduser().resolve()

INPUT_PATH = env_path('RESEARCH_INPUT', Path.cwd() / 'other-b.json')
OUTPUT_DIR = env_path('RESEARCH_OUTPUT_DIR', Path.cwd() / 'research-output')
CACHE_DIR = env_path('RESEARCH_CACHE_DIR', OUTPUT_DIR / 'private-cache')
RESULT_PATH = env_path('RESEARCH_RESULT', OUTPUT_DIR / 'enriched-other-b.json')
PARTIAL_PATH = env_path('RESEARCH_PARTIAL', OUTPUT_DIR / 'enriched-other-b.partial.json')
AUDIT_PATH = env_path('RESEARCH_AUDIT', OUTPUT_DIR / 'audit-other-b.json')
CHECKED_AT = os.environ.get('RESEARCH_CHECKED_AT', date.today().isoformat())
date.fromisoformat(CHECKED_AT)
LEGACY_DIR = env_path('RESEARCH_LEGACY_DIR', '.') if os.environ.get('RESEARCH_LEGACY_DIR') else None
MAX_WORKERS = min(6, max(1, int(os.environ.get('RESEARCH_MAX_WORKERS', '6'))))
HOST_CONCURRENCY = min(2, max(1, int(os.environ.get('RESEARCH_HOST_CONCURRENCY', '2'))))
HTTP_TIMEOUT = float(os.environ.get('RESEARCH_HTTP_TIMEOUT', '12'))
if HTTP_TIMEOUT <= 0:
    raise ValueError('RESEARCH_HTTP_TIMEOUT must be positive')
MAYORS_FACTS_PATH = env_path('RESEARCH_MAYORS_FACTS', PACKAGE_DIR / 'reviewed-mayors-2026-11-05.json')
MAYORS_INPUT_PATH = env_path('RESEARCH_MAYORS_INPUT', PACKAGE_DIR / 'mayors-targets-2025-04-30.json')
MAYORS_OUTPUT_PATH = env_path('RESEARCH_MAYORS_OUTPUT', OUTPUT_DIR / 'enriched-mayors-web-followup.json')

def prepare_output():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for p in (RESULT_PATH, PARTIAL_PATH, AUDIT_PATH, MAYORS_OUTPUT_PATH):
        p.parent.mkdir(parents=True, exist_ok=True)

def require_snapshot_curations():
    if os.environ.get('RESEARCH_USE_SNAPSHOT_CURATIONS') != '1' or CHECKED_AT != '2026-11-05':
        raise RuntimeError(
            'These reviewed summaries apply only to the 2026-11-05 snapshot. '
            'Re-check the source facts first; to replay that snapshot explicitly set '
            'RESEARCH_USE_SNAPSHOT_CURATIONS=1 and RESEARCH_CHECKED_AT=2026-11-05.'
        )


def load_people():
    import json
    import re
    people = json.loads(INPUT_PATH.read_text(encoding='utf-8'))
    if not isinstance(people, list):
        raise ValueError('RESEARCH_INPUT must contain a JSON array')
    identifiers = set()
    for person in people:
        if not isinstance(person, dict) or not isinstance(person.get('id'), str) or not person.get('id'):
            raise ValueError('Every input person requires a nonempty string id')
        if person['id'] in identifiers:
            raise ValueError('Duplicate input id: ' + person['id'])
        identifiers.add(person['id'])
        if not isinstance(person.get('name'), str) or not person['name'].strip():
            raise ValueError('Every input person requires a name')
        if not re.fullmatch(r'\d{5}', str(person.get('municipalityCode', ''))):
            raise ValueError('municipalityCode must be five digits: ' + person['id'])
        aliases = person.get('sourceNames', [])
        if not isinstance(aliases, list) or not all(isinstance(n, str) for n in aliases):
            raise ValueError('sourceNames must be a list of verified name strings')
    return people
