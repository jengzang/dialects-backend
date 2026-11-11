#!/usr/bin/env python3
"""Explicit supplements migration. Default is read-only inspection; never imports app DB.

Back up the selected database before --apply. Stop old writers before enabling
version enforcement. --cleanup-receipts deletes at most 100 expired receipts.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import re
from pathlib import Path
import sqlite3


@contextmanager
def _connect(path, write=False):
    path = Path(path).resolve(strict=True)
    connection = sqlite3.connect(f'{path.as_uri()}?mode={"rw" if write else "ro"}', uri=True, timeout=5)
    try:
        yield connection
    finally:
        connection.close()


def _quote(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def _split_definitions(body):
    """Split CREATE TABLE definitions without splitting expressions/quoted text."""
    result, start, depth, quote, i = [], 0, 0, None, 0
    while i < len(body):
        ch = body[i]
        if quote:
            end = ']' if quote == '[' else quote
            if ch == end:
                if i + 1 < len(body) and body[i + 1] == end and end != ']':
                    i += 1
                else:
                    quote = None
        elif ch in ('"', "'", '`', '['):
            quote = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            result.append(body[start:i].strip())
            start = i + 1
        i += 1
    result.append(body[start:].strip())
    if quote or depth:
        raise ValueError('Unsupported CREATE TABLE syntax; migration aborted')
    return result


def ensure_autoincrement(conn):
    """Rebuild only when needed, preserving original DDL, indexes, and triggers.

    Inbound foreign references require a separately reviewed migration; aborting
    leaves the entire transaction intact. Unknown columns are copied in SQLite,
    never loaded into Python memory.
    """
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='informations'").fetchone()[0]
    if re.search(r'\bAUTOINCREMENT\b', sql, re.I):
        return
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for table in tables:
        if any(row[2] == 'informations' for row in conn.execute(f'PRAGMA foreign_key_list({_quote(table)})')):
            raise ValueError('Inbound foreign key references informations; migration requires manual review')
    columns = list(conn.execute('PRAGMA table_xinfo(informations)'))
    pk = [row for row in columns if row[5]]
    if len(pk) != 1 or pk[0][1] != 'id' or pk[0][2].upper() != 'INTEGER':
        raise ValueError('Unsupported informations primary key; migration aborted')
    if re.search(r'\bWITHOUT\s+ROWID\b', sql, re.I) or '--' in sql or '/*' in sql:
        raise ValueError('Unsupported informations DDL; migration aborted')
    start, end = sql.index('('), sql.rfind(')')
    definitions = _split_definitions(sql[start + 1:end])
    id_name = r'(?:id|"id"|`id`|\[id\])'
    table_pk = re.compile(r'^(?:CONSTRAINT\s+\S+\s+)?PRIMARY\s+KEY\s*\(\s*' + id_name + r'\s*\)$', re.I)
    table_keys = [part for part in definitions if table_pk.fullmatch(part)]
    definitions = [part for part in definitions if not table_pk.fullmatch(part)]
    found = False
    for i, part in enumerate(definitions):
        if re.match(r'^' + id_name + r'\s+INTEGER\b', part, re.I):
            if re.search(r'\bPRIMARY\s+KEY\b', part, re.I):
                if re.search(r'\bPRIMARY\s+KEY\s+(?:ASC|DESC|ON)\b', part, re.I):
                    raise ValueError('Unsupported inline primary key; migration aborted')
                part = re.sub(r'\bPRIMARY\s+KEY\b', 'PRIMARY KEY AUTOINCREMENT', part, count=1, flags=re.I)
            elif len(table_keys) == 1:
                part += ' PRIMARY KEY AUTOINCREMENT'
            else:
                raise ValueError('Unrecognized primary key declaration; migration aborted')
            definitions[i] = part
            found = True
            break
    if not found:
        raise ValueError('Unrecognized id column; migration aborted')
    temp = 'informations_custom_safety_migration'
    if conn.execute('SELECT 1 FROM sqlite_master WHERE name=?', (temp,)).fetchone():
        raise ValueError('Migration temporary table already exists; review before continuing')
    extra_ddl = [row[0] for row in conn.execute("SELECT sql FROM sqlite_master WHERE tbl_name='informations' AND type IN ('index','trigger') AND sql IS NOT NULL")]
    before = conn.execute('SELECT COUNT(*), MAX(id) FROM informations').fetchone()
    conn.execute(f'CREATE TABLE {_quote(temp)} (' + ', '.join(definitions) + ')' + sql[end + 1:])
    writable = ','.join(_quote(row[1]) for row in columns if row[6] == 0)
    conn.execute(f'INSERT INTO {_quote(temp)} ({writable}) SELECT {writable} FROM informations')
    after = conn.execute(f'SELECT COUNT(*), MAX(id) FROM {_quote(temp)}').fetchone()
    if before != after:
        raise ValueError('Migration row count/identity verification failed')
    conn.execute('DROP TABLE informations')
    conn.execute(f'ALTER TABLE {_quote(temp)} RENAME TO informations')
    for statement in extra_ddl:
        conn.execute(statement)


def inspect_schema(path):
    with _connect(path) as conn:
        columns = {row[1]: row for row in conn.execute('PRAGMA table_info(informations)')}
        receipts = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='custom_mutation_receipts'").fetchone() is not None
        indexes = {row[1] for row in conn.execute('PRAGMA index_list(custom_mutation_receipts)')}
        invalid_versions = None
        if 'version' in columns:
            invalid_versions = conn.execute('SELECT COUNT(*) FROM informations WHERE version IS NULL OR version < 1').fetchone()[0]
        original_sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='informations' AND type='table'").fetchone()
        monotonic_ids = bool(original_sql and re.search(r'\bAUTOINCREMENT\b', original_sql[0], re.I))
        version_ready = 'version' in columns and bool(columns['version'][3]) and invalid_versions == 0
        return {'ready': version_ready and monotonic_ids and receipts and 'idx_custom_receipt_created_at' in indexes,
                'monotonic_ids': monotonic_ids, 'version_column': 'version' in columns, 'invalid_versions': invalid_versions, 'receipt_table': receipts}


def migrate(path):
    with _connect(path, write=True) as conn:
        conn.execute('PRAGMA legacy_alter_table=ON')
        conn.execute('BEGIN IMMEDIATE')
        try:
            columns = {row[1] for row in conn.execute('PRAGMA table_info(informations)')}
            if not columns:
                raise ValueError('informations table does not exist; select the existing supplements database')
            ensure_autoincrement(conn)
            if 'version' not in columns:
                conn.execute('ALTER TABLE informations ADD COLUMN version INTEGER NOT NULL DEFAULT 1')
            conn.execute('CREATE TABLE IF NOT EXISTS custom_mutation_receipts ('
                         'id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, request_id VARCHAR(36) NOT NULL, '
                         'request_hash VARCHAR(64) NOT NULL, result_json TEXT NOT NULL, created_at DATETIME NOT NULL, '
                         'CONSTRAINT uq_custom_receipt_user_request UNIQUE (user_id, request_id))')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_custom_receipt_created_at ON custom_mutation_receipts (created_at)')
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return inspect_schema(path)


def cleanup_receipts(path):
    cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)).isoformat(sep=' ')
    with _connect(path, write=True) as conn:
        conn.execute('BEGIN IMMEDIATE')
        try:
            count = conn.execute('DELETE FROM custom_mutation_receipts WHERE id IN ('
                                 'SELECT id FROM custom_mutation_receipts WHERE created_at < ? '
                                 'ORDER BY created_at LIMIT 100)', (cutoff,)).rowcount
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return {'deleted_receipts': count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, help='Explicit path to an existing supplements SQLite database')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--check', action='store_true', help='Read-only schema inspection (default)')
    action.add_argument('--apply', action='store_true', help='Explicitly apply migration after taking a backup')
    action.add_argument('--cleanup-receipts', action='store_true', help='Delete at most 100 expired receipt rows')
    args = parser.parse_args()
    result = migrate(args.database) if args.apply else cleanup_receipts(args.database) if args.cleanup_receipts else inspect_schema(args.database)
    print(json.dumps(result, ensure_ascii=False))
    if 'ready' in result and not result['ready']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
