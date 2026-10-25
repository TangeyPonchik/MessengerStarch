"""
database.py — SQLite-хранилище Starch.
"""

import sqlite3
import threading
import sys
import os
from datetime import datetime

# Определяем, где лежит .exe или .py
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "starch.db")
_lock = threading.Lock()

LAZUR_USER_ID = 999


def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _lock:
        c = _conn()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user INTEGER NOT NULL,
            to_user INTEGER,
            text TEXT NOT NULL,
            reply_to INTEGER,
            edited INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            delivered INTEGER DEFAULT 1,
            read INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            emoji TEXT NOT NULL,
            UNIQUE(message_id, user_id, emoji)
        );
        CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(from_user, to_user);
        """)
        c.commit()

        # Виртуальный пользователь Lazur
        c.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash, created_at) "
            "VALUES (?, ?, ?, ?)",
            (LAZUR_USER_ID, "lazur-lite", "none", datetime.now().isoformat())
        )
        c.commit()
        c.close()


def register_user(username: str, password_hash: str):
    with _lock:
        c = _conn()
        try:
            cur = c.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, datetime.now().isoformat())
            )
            c.commit()
            uid = cur.lastrowid
            c.close()
            return uid, None
        except sqlite3.IntegrityError:
            c.close()
            return None, "Логин уже занят"


def get_user_by_username(username: str):
    with _lock:
        c = _conn()
        row = c.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        c.close()
        return dict(row) if row else None


def get_user_by_id(uid: int):
    with _lock:
        c = _conn()
        row = c.execute("SELECT id, username FROM users WHERE id = ?", (uid,)).fetchone()
        c.close()
        return dict(row) if row else None


def save_message(from_user: int, to_user, text: str, reply_to=None) -> dict:
    with _lock:
        c = _conn()
        cur = c.execute(
            "INSERT INTO messages (from_user, to_user, text, reply_to, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (from_user, to_user, text, reply_to, datetime.now().isoformat())
        )
        c.commit()
        mid = cur.lastrowid
        row = c.execute("SELECT * FROM messages WHERE id = ?", (mid,)).fetchone()
        c.close()
        return dict(row)


def get_history(user_id: int, peer_id, limit: int = 100):
    with _lock:
        c = _conn()
        if peer_id is None:
            rows = c.execute("""
                SELECT m.*, u.username as from_name FROM messages m
                JOIN users u ON u.id = m.from_user
                WHERE m.to_user IS NULL AND m.deleted = 0
                ORDER BY m.id DESC LIMIT ?
            """, (limit,)).fetchall()
        elif peer_id == LAZUR_USER_ID:
            rows = c.execute("""
                SELECT m.*, u.username as from_name FROM messages m
                JOIN users u ON u.id = m.from_user
                WHERE m.deleted = 0 AND (
                    (m.from_user = ? AND m.to_user = ?) OR
                    (m.from_user = ? AND m.to_user = ?)
                )
                ORDER BY m.id DESC LIMIT ?
            """, (user_id, LAZUR_USER_ID, LAZUR_USER_ID, user_id, limit)).fetchall()
        else:
            rows = c.execute("""
                SELECT m.*, u.username as from_name FROM messages m
                JOIN users u ON u.id = m.from_user
                WHERE m.deleted = 0 AND m.to_user IS NOT NULL AND (
                    (m.from_user = ? AND m.to_user = ?) OR
                    (m.from_user = ? AND m.to_user = ?)
                )
                ORDER BY m.id DESC LIMIT ?
            """, (user_id, peer_id, peer_id, user_id, limit)).fetchall()
        c.close()
        return [dict(r) for r in reversed(rows)]


def edit_message(message_id: int, user_id: int, new_text: str) -> bool:
    with _lock:
        c = _conn()
        cur = c.execute(
            "UPDATE messages SET text = ?, edited = 1 WHERE id = ? AND from_user = ? AND deleted = 0",
            (new_text, message_id, user_id)
        )
        c.commit()
        affected = cur.rowcount
        c.close()
        return affected > 0


def delete_message(message_id: int, user_id: int) -> bool:
    with _lock:
        c = _conn()
        cur = c.execute(
            "UPDATE messages SET deleted = 1 WHERE id = ? AND from_user = ?",
            (message_id, user_id)
        )
        c.commit()
        affected = cur.rowcount
        c.close()
        return affected > 0


def toggle_reaction(message_id: int, user_id: int, emoji: str):
    with _lock:
        c = _conn()
        row = c.execute(
            "SELECT id FROM reactions WHERE message_id = ? AND user_id = ? AND emoji = ?",
            (message_id, user_id, emoji)
        ).fetchone()
        if row:
            c.execute("DELETE FROM reactions WHERE id = ?", (row["id"],))
            added = False
        else:
            c.execute(
                "INSERT INTO reactions (message_id, user_id, emoji) VALUES (?, ?, ?)",
                (message_id, user_id, emoji)
            )
            added = True
        c.commit()
        c.close()
        return added


def get_reactions(message_id: int):
    with _lock:
        c = _conn()
        rows = c.execute(
            "SELECT emoji, COUNT(*) as cnt FROM reactions WHERE message_id = ? GROUP BY emoji",
            (message_id,)
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]


def get_all_users(except_id: int = None):
    with _lock:
        c = _conn()
        if except_id:
            rows = c.execute(
                "SELECT id, username FROM users WHERE id != ? AND id != ?",
                (except_id, LAZUR_USER_ID)
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id, username FROM users WHERE id != ?",
                (LAZUR_USER_ID,)
            ).fetchall()
        c.close()
        return [dict(r) for r in rows]


def search_messages(user_id: int, peer_id, query: str, limit: int = 50):
    with _lock:
        c = _conn()
        q = f"%{query}%"
        if peer_id is None:
            rows = c.execute("""
                SELECT m.*, u.username as from_name FROM messages m
                JOIN users u ON u.id = m.from_user
                WHERE m.to_user IS NULL AND m.deleted = 0 AND m.text LIKE ?
                ORDER BY m.id DESC LIMIT ?
            """, (q, limit)).fetchall()
        else:
            rows = c.execute("""
                SELECT m.*, u.username as from_name FROM messages m
                JOIN users u ON u.id = m.from_user
                WHERE m.deleted = 0 AND m.text LIKE ? AND m.to_user IS NOT NULL AND (
                    (m.from_user = ? AND m.to_user = ?) OR
                    (m.from_user = ? AND m.to_user = ?)
                )
                ORDER BY m.id DESC LIMIT ?
            """, (q, user_id, peer_id, peer_id, user_id, limit)).fetchall()
        c.close()
        return [dict(r) for r in reversed(rows)]