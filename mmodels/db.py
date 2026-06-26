"""
ProveIt Database
SQLite (local dev) → PostgreSQL (production/Render)
Auto-detects based on DATABASE_URL env var
"""

import os
import sqlite3
from flask import g

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    # Render gives postgres:// but psycopg2 needs postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


class PGConnWrapper:
    """
    Wraps a psycopg2 connection so route code written for sqlite3
    (db.execute(sql_with_question_marks, params) -> cursor with
    .fetchone()/.fetchall() returning dict-like rows) works unchanged.
    """
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        # sqlite3 uses "?" placeholders, psycopg2 uses "%s"
        pg_sql = sql.replace("?", "%s")
        # SQLite-specific function not valid in Postgres
        pg_sql = pg_sql.replace("datetime('now')", "NOW()")
        cur = self._conn.cursor()
        cur.execute(pg_sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_db(app=None):
    """Get a DB connection. Same .execute()/.commit() API regardless of engine."""
    if USE_POSTGRES:
        if "db" not in g:
            raw = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
            g.db = PGConnWrapper(raw)
        return g.db
    else:
        if app:
            db = sqlite3.connect(app.config["DATABASE"])
            db.row_factory = sqlite3.Row
            return db
        if "db" not in g:
            from flask import current_app
            g.db = sqlite3.connect(current_app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()


# SQL written once, generic enough for both engines.
# Postgres: TIMESTAMP DEFAULT NOW() / SQLite: TEXT DEFAULT (datetime('now'))
def _ts_default():
    return "TIMESTAMP DEFAULT NOW()" if USE_POSTGRES else "TEXT DEFAULT (datetime('now'))"


def init_db(app):
    with app.app_context():
        if USE_POSTGRES:
            conn = psycopg2.connect(DATABASE_URL)
        else:
            conn = sqlite3.connect(app.config["DATABASE"])
        cur = conn.cursor()
        ts = _ts_default()

        cur.execute(f"""CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            display_name TEXT NOT NULL,
            avatar_emoji TEXT DEFAULT '⚡',
            bio TEXT DEFAULT '',
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            interests TEXT DEFAULT '[]',
            created_at {ts}
        )""")

        cur.execute(f"""CREATE TABLE IF NOT EXISTS challenges (
            id TEXT PRIMARY KEY,
            creator_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT 'عمومی',
            tags TEXT DEFAULT '[]',
            proof_type TEXT DEFAULT 'photo',
            duration_hours INTEGER DEFAULT 24,
            xp_reward INTEGER DEFAULT 100,
            is_public INTEGER DEFAULT 1,
            participants_count INTEGER DEFAULT 0,
            created_at {ts}
        )""")

        cur.execute(f"""CREATE TABLE IF NOT EXISTS user_challenges (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            challenge_id TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            proof_url TEXT DEFAULT '',
            xp_earned INTEGER DEFAULT 0,
            started_at {ts},
            completed_at {"TIMESTAMP" if USE_POSTGRES else "TEXT"}
        )""")

        cur.execute(f"""CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            challenge_id TEXT,
            caption TEXT DEFAULT '',
            media_url TEXT DEFAULT '',
            media_type TEXT DEFAULT 'image',
            likes_count INTEGER DEFAULT 0,
            cheers_count INTEGER DEFAULT 0,
            comments_count INTEGER DEFAULT 0,
            created_at {ts}
        )""")

        cur.execute(f"""CREATE TABLE IF NOT EXISTS friendships (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            friend_id TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at {ts}
        )""")

        cur.execute(f"""CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            sender_id TEXT NOT NULL,
            receiver_id TEXT NOT NULL,
            content TEXT NOT NULL,
            type TEXT DEFAULT 'text',
            challenge_id TEXT,
            is_read INTEGER DEFAULT 0,
            created_at {ts}
        )""")

        cur.execute(f"""CREATE TABLE IF NOT EXISTS images (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at {ts}
        )""")

        cur.execute(f"""CREATE TABLE IF NOT EXISTS likes (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            post_id TEXT NOT NULL,
            type TEXT DEFAULT 'like',
            created_at {ts},
            UNIQUE(user_id, post_id, type)
        )""")

        conn.commit()
        conn.close()
        print("✅ Database initialized" + (" (PostgreSQL)" if USE_POSTGRES else " (SQLite)"))
