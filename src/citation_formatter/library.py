"""Store saved sources, detect duplicates, and support one-step undo.

SQLite is included in Python. Existing library.json/overrides.json files are
imported once on first use; those original files are never modified.
"""
import hashlib
import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from .citations import clean_input
from .output import format_source
from .validation import normalize_fields

# Keep personal records outside the importable package. Running from the project
# root uses its data folder; an installed copy falls back to a private home folder.
if os.environ.get('CITATION_DATA_DIR'):
    DATA_DIR = Path(os.environ['CITATION_DATA_DIR'])
elif (Path.cwd() / 'pyproject.toml').is_file():
    DATA_DIR = Path.cwd() / 'data'
else:
    DATA_DIR = Path.home() / '.quickcite'
HEADINGS = {'APA': 'References', 'MLA': 'Works Cited', 'Chicago': 'Bibliography'}


class StorageError(RuntimeError):
    pass


class DuplicateSource(ValueError):
    def __init__(self, entry_id):
        super().__init__('This source is already saved. Use Edit to update it.')
        self.entry_id = entry_id


class SourceNotFound(ValueError):
    pass


def normalized_text(value):
    return ' '.join(value.casefold().split())


def fingerprint(fields):
    """Prefer persistent identifiers; keep editions distinct for manual sources."""
    if fields.get('doi'):
        key = ('doi', normalized_text(fields['doi']))
    elif fields.get('isbn'):
        key = ('isbn', re.sub(r'[^0-9Xx]', '', fields['isbn']).upper())
    else:
        data = clean_input(fields)
        people = data['authors'] or (data['editors'] if data['source_type'] == 'book' else [])
        author_key = tuple((normalized_text(p['last']), normalized_text(p['given']), p.get('suffix', '')) for p in people)
        key = (fields['source_type'], author_key,
               *(normalized_text(fields.get(k, '')) for k in ('title', 'container', 'year', 'edition', 'publisher')))
    return hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest()


def _migrate(connection):
    if connection.execute("SELECT 1 FROM metadata WHERE key='legacy_imported'").fetchone():
        return
    path = DATA_DIR / 'library.json'
    corrections = DATA_DIR / 'overrides.json'
    try:
        entries = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
        overrides = json.loads(corrections.read_text(encoding='utf-8')) if corrections.exists() else {}
        if not isinstance(entries, list) or not isinstance(overrides, dict):
            raise ValueError('Unexpected JSON structure.')
        for entry in entries:
            raw = dict(entry['fields'])
            raw['case_overrides'] = overrides | raw.get('case_overrides', {})
            fields = normalize_fields(raw, saving=True)
            format_source(fields)  # Do not import an entry that cannot be rendered.
            connection.execute('INSERT INTO sources(id, fields, fingerprint) VALUES (?, ?, ?)',
                               (uuid.uuid4().hex, json.dumps(fields, ensure_ascii=False),
                                fingerprint(fields)))
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise StorageError('Could not import the old JSON files. They were left untouched. '
                           'See the data recovery section in RUN_GUIDE.md.') from error
    connection.execute("INSERT INTO metadata(key, value) VALUES ('legacy_imported', '1')")


@contextmanager
def database():
    connection = None
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(DATA_DIR / 'library.sqlite3', timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA busy_timeout=10000')
        connection.execute('BEGIN IMMEDIATE')
        connection.execute('CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        connection.execute('CREATE TABLE IF NOT EXISTS sources('
                           'id TEXT PRIMARY KEY, fields TEXT NOT NULL, fingerprint TEXT NOT NULL, '
                           'deleted INTEGER NOT NULL DEFAULT 0)')
        connection.execute(
            'CREATE INDEX IF NOT EXISTS source_fingerprint_idx '
            'ON sources(fingerprint, deleted)'
        )
        _migrate(connection)
        yield connection
        connection.commit()
    except (sqlite3.Error, OSError) as error:
        if connection:
            connection.rollback()
        raise StorageError('The saved sources could not be read or written. '
                           'Your existing data was not replaced. See RUN_GUIDE.md.') from error
    except Exception:
        if connection:
            connection.rollback()
        raise
    finally:
        if connection:
            connection.close()


def load():
    with database() as connection:
        rows = connection.execute('SELECT id, fields FROM sources WHERE deleted=0 ORDER BY rowid').fetchall()
        try:
            return [{'id': row['id'], 'fields': normalize_fields(json.loads(row['fields']), saving=True)} for row in rows]
        except (ValueError, TypeError) as error:
            raise StorageError('A saved source is invalid. The database has been preserved; see RUN_GUIDE.md.') from error


def upsert(raw, entry_id=None):
    fields = normalize_fields(raw, saving=True)
    format_source(fields)
    key = fingerprint(fields)
    with database() as connection:
        if entry_id and not connection.execute('SELECT 1 FROM sources WHERE id=? AND deleted=0', (entry_id,)).fetchone():
            raise SourceNotFound('This source is no longer in the list. Reload the list and try again.')
        duplicate = connection.execute('SELECT id FROM sources WHERE fingerprint=? AND deleted=0 AND id!=?',
                                       (key, entry_id or '')).fetchone()
        if duplicate:
            raise DuplicateSource(duplicate['id'])
        if entry_id:
            connection.execute('UPDATE sources SET fields=?, fingerprint=? WHERE id=?',
                               (json.dumps(fields, ensure_ascii=False), key, entry_id))
        else:
            entry_id = uuid.uuid4().hex
            connection.execute('INSERT INTO sources(id, fields, fingerprint) VALUES (?, ?, ?)',
                               (entry_id, json.dumps(fields, ensure_ascii=False), key))
    return entry_id


def remove(entry_id):
    with database() as connection:
        if entry_id == '*':
            rows = connection.execute('SELECT id FROM sources WHERE deleted=0').fetchall()
        else:
            rows = connection.execute('SELECT id FROM sources WHERE id=? AND deleted=0', (entry_id,)).fetchall()
        ids = [row['id'] for row in rows]
        connection.executemany('UPDATE sources SET deleted=1 WHERE id=?', [(item,) for item in ids])
    return ids


def restore(ids):
    with database() as connection:
        for entry_id in ids:
            row = connection.execute('SELECT fingerprint FROM sources WHERE id=? AND deleted=1', (entry_id,)).fetchone()
            if not row:
                continue
            duplicate = connection.execute('SELECT id FROM sources WHERE fingerprint=? AND deleted=0',
                                           (row['fingerprint'],)).fetchone()
            if duplicate:
                raise DuplicateSource(duplicate['id'])
            connection.execute('UPDATE sources SET deleted=0 WHERE id=?', (entry_id,))


def sort_key(entry, style='APA'):
    data = clean_input(entry['fields'])
    people = data['authors'] or (data['editors'] if data['source_type'] == 'book' else [])
    title = re.sub(r'^(a|an|the)\s+', '', data['title'], flags=re.I).casefold()
    names = tuple((p['last'].casefold(), p['given'].casefold()) for p in people) or ((title, ''),)
    if style == 'APA':
        return names, data['year'], title
    return names, title, data['year']


def presentation(style):
    entries = []
    for entry in sorted(load(), key=lambda item: sort_key(item, style)):
        citation = format_source(entry['fields'])['styles'][style]
        entries.append({'id': entry['id'], 'fields': entry['fields'], **citation})
    heading = HEADINGS[style]
    return {'count': len(entries), 'style': style, 'heading': heading, 'entries': entries,
            'plain': '\n\n'.join(entry['text'] for entry in entries),
            'html': ''.join('<p style="margin:0;line-height:2;padding-left:0.5in;text-indent:-0.5in">' +
                            entry['html'] + '</p>' for entry in entries)}
