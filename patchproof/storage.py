"""Transactional local adapter. AWS uses the same immutable capsule contract."""
from pathlib import Path
from contextlib import contextmanager
import sqlite3

from .capsule import canonical, load, verify


class StoreError(RuntimeError):
    pass


def metadata(report):
    payload = report['payload']
    return {'id': report['sha256'], 'title': payload['title'], 'project': payload['project'],
            'createdAt': payload['createdAt'], 'comparison': payload['comparison']}


class LocalStore:
    def __init__(self, directory):
        Path(directory).mkdir(parents=True, exist_ok=True)
        self.path = Path(directory) / 'reports.sqlite3'
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, created TEXT NOT NULL, capsule BLOB NOT NULL)')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=20)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def put(self, report):
        identity = verify(report)
        with self.connect() as db:
            cursor = db.execute('INSERT OR IGNORE INTO reports VALUES (?,?,?)',
                                (identity, report['payload']['createdAt'], canonical(report)))
            existing = db.execute('SELECT capsule FROM reports WHERE id=?', (identity,)).fetchone()[0]
            if bytes(existing) != canonical(report):
                raise StoreError('Stored content differs from its identity')
            return cursor.rowcount == 1

    def get(self, identity):
        with self.connect() as db:
            row = db.execute('SELECT capsule FROM reports WHERE id=?', (identity,)).fetchone()
        if row is None:
            return None
        try:
            report = load(bytes(row[0]))
            if report['sha256'] != identity:
                raise StoreError('Stored identity differs')
            return report
        except ValueError as error:
            raise StoreError('Stored content failed verification') from error

    def list(self):
        with self.connect() as db:
            rows = db.execute('SELECT id FROM reports ORDER BY created DESC, id DESC LIMIT 25').fetchall()
        return [metadata(self.get(row[0])) for row in rows]
