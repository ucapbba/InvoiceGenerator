"""SQLite storage: the client rows (Generator sheet), generated invoices (the tabs) and users."""

import sqlite3
from contextlib import closing
from datetime import date

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until REAL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY,
    position INTEGER NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    amount TEXT NOT NULL DEFAULT '',
    property TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL DEFAULT 'Unit',
    email TEXT NOT NULL DEFAULT '',
    count INTEGER
);
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY,
    sheet_name TEXT NOT NULL UNIQUE,
    invoice_id TEXT NOT NULL,
    invoice_date TEXT NOT NULL,
    client TEXT NOT NULL,
    address TEXT NOT NULL,
    property TEXT NOT NULL,
    type TEXT NOT NULL,
    email TEXT NOT NULL,
    net TEXT NOT NULL,
    vat TEXT NOT NULL,
    total TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

# Made-up clients so the app has something to work with. Not real people.
SAMPLE_CLIENTS = [
    ("Ms A Sample", "300", "Example Farm Unit 1", "1 Sample Street,Anytown,Countyshire,AB1 1AA", "Unit", "a.sample@example.com"),
    ("Mr B Example", "450", "Example Farm Unit 2", "22 Example Road,Othertown,Countyshire,AB2 2BB", "Unit", "b.example@example.com"),
    ("Mrs C Smith", "250", "Example Farm Unit 3", "3 Test Lane,Anytown,AB1 3CC", "Unit", "c.smith@example.com"),
    ("Mr D Smith", "333.33", "Example Farm Unit 4", "Smith Workshops,4 Demo Way,Othertown,AB2 4DD", "Unit", ""),
    ("Dr E Placeholder", "1050", "Example Farm Unit 5", "5 Mock Close,Sampleton,AB3 5EE", "Unit", "e.placeholder@example.com"),
    ("Mr F Tenant", "900", "Example Cottage", "Example Cottage,Sample Lane,Anytown,AB1 6FF", "House", "f.tenant@example.com"),
]


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(path: str):
    with closing(sqlite3.connect(path)) as con, con:
        con.executescript(SCHEMA)
        if con.execute("SELECT COUNT(*) FROM settings").fetchone()[0]:
            return
        con.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", [
            ("invoice_date", date.today().isoformat()),
            ("next_number", "1"),
        ])
        con.executemany(
            "INSERT INTO clients (position, name, amount, property, address, type, email) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(i, *client) for i, client in enumerate(SAMPLE_CLIENTS, start=1)],
        )


def get_settings(db) -> dict:
    return {row["key"]: row["value"] for row in db.execute("SELECT key, value FROM settings")}


def set_setting(db, key: str, value):
    db.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
               (key, str(value)))


def init_app(app):
    init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)
