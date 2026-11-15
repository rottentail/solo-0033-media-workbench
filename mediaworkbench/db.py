"""Persistent state for the media processing service."""
import sqlite3

SCHEMA = '''
CREATE TABLE IF NOT EXISTS assets (id INTEGER PRIMARY KEY, path TEXT NOT NULL, fingerprint TEXT NOT NULL, metadata TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY, name TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS clips (id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id), asset_id INTEGER NOT NULL REFERENCES assets(id), start_ms INTEGER NOT NULL, end_ms INTEGER NOT NULL, position INTEGER NOT NULL, gain REAL NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS renders (id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL, status TEXT NOT NULL, snapshot TEXT NOT NULL, output_path TEXT, error TEXT);
'''

def connect(path):
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.executescript(SCHEMA)
    return conn
