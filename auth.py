from core.logger import logger
import sqlite3
import hashlib
import secrets
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conversations.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_auth():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
    """)
    conn.commit()
    # Create default admin user if no users exist
    count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    if count == 0:
        create_user("kiran", "kiran123")
        logger.info("  Default user created: kiran / kiran123")
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
            (username.lower(), hash_password(password), datetime.now().isoformat())
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login(username, password):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND password_hash=?",
        (username.lower(), hash_password(password))
    ).fetchone()
    if not user:
        conn.close()
        return None
    # Create session token
    token = secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(days=7)).isoformat()
    conn.execute(
        "INSERT INTO sessions (token, user_id, username, expires_at) VALUES (?,?,?,?)",
        (token, user["id"], user["username"], expires)
    )
    conn.commit()
    conn.close()
    return {"token": token, "username": user["username"]}

def verify_token(token):
    if not token:
        return None
    conn = get_db()
    session = conn.execute(
        "SELECT * FROM sessions WHERE token=?", (token,)
    ).fetchone()
    conn.close()
    if not session:
        return None
    if datetime.fromisoformat(session["expires_at"]) < datetime.now():
        return None
    return {"username": session["username"], "user_id": session["user_id"]}

def logout(token):
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_db()
    users = conn.execute("SELECT id, username, created_at FROM users").fetchall()
    conn.close()
    return [dict(u) for u in users]

def delete_user(username):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()