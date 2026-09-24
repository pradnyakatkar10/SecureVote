"""
database/db.py
---------------
Relational storage for everything that is NOT the vote ledger itself:
who is registered, what elections and candidates exist, and (deliberately
minimal) *that* a given user voted in a given election -- never *for whom*.
Who someone voted for lives only on the blockchain, keyed by a one-way
hash of their identity (see blockchain/block.py and voter_hash below).
"""

import hashlib
import os
import sqlite3

from werkzeug.security import generate_password_hash

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(APP_DIR, "data", "voting.db")

DEFAULT_ADMIN_STUDENT_ID = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


def voter_hash_for(student_id):
    return hashlib.sha256(student_id.strip().lower().encode()).hexdigest()


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            student_id TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            voter_hash TEXT UNIQUE NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS elections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            status TEXT NOT NULL DEFAULT 'pending'  -- pending | active | ended
        );

        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            election_id INTEGER NOT NULL REFERENCES elections(id),
            name TEXT NOT NULL,
            party TEXT,
            contract_candidate_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            election_id INTEGER NOT NULL REFERENCES elections(id),
            blockchain_tx_hash TEXT,
            UNIQUE(user_id, election_id)
        );
        """
    )
    # Lightweight migration for databases created by the earlier version.
    for table, column, definition in [
        ("candidates", "contract_candidate_id", "INTEGER"),
        ("votes", "blockchain_tx_hash", "TEXT"),
    ]:
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    conn.commit()

    existing_admin = conn.execute("SELECT id FROM users WHERE is_admin = 1").fetchone()
    if not existing_admin:
        conn.execute(
            "INSERT INTO users (name, student_id, email, password_hash, voter_hash, is_admin) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (
                "Administrator",
                DEFAULT_ADMIN_STUDENT_ID,
                "admin@voting.local",
                generate_password_hash(DEFAULT_ADMIN_PASSWORD),
                voter_hash_for(DEFAULT_ADMIN_STUDENT_ID),
            ),
        )
        conn.commit()
    conn.close()
