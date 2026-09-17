import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT, created TEXT, body TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, body TEXT)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / 'project.sqlite3', timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def unresolved_run(self):
        """Safety checks must inspect all journals, not a paginated history."""
        with self.connect() as db:
            rows = db.execute("SELECT id, body FROM records WHERE kind='run' ORDER BY created")
            for row in rows:
                if json.loads(row['body'])['status'] in {'executing', 'needs_recovery', 'undoing'}:
                    return row['id']
        return None

    def add(self, kind, body):
        identity = uuid.uuid4().hex
        with self.connect() as db:
            db.execute('INSERT INTO records VALUES (?,?,?,?)',
                       (identity, kind, datetime.now(timezone.utc).isoformat(), json.dumps(body, allow_nan=False)))
        return identity

    def get(self, identity, kind=None):
        with self.connect() as db:
            row = db.execute('SELECT * FROM records WHERE id=?', (identity,)).fetchone()
        if not row or (kind and row['kind'] != kind):
            raise ValueError('Unknown record or incorrect record type: ' + identity)
        return dict(row, body=json.loads(row['body']))

    def update(self, identity, body):
        with self.connect() as db:
            if db.execute('UPDATE records SET body=? WHERE id=?',
                          (json.dumps(body, allow_nan=False), identity)).rowcount != 1:
                raise ValueError('Unknown record: ' + identity)

    def list(self, kind, limit=20):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM records WHERE kind=? ORDER BY created DESC LIMIT ?',
                              (kind, max(1, min(int(limit), 200)))).fetchall()
        return [dict(r, body=json.loads(r['body'])) for r in rows]

    def setting(self, key, value=None):
        with self.connect() as db:
            if value is not None:
                db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value, allow_nan=False)))
            row = db.execute('SELECT body FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None
