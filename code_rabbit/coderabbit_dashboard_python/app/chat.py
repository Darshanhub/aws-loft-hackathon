# app/chat.py
import aiosqlite
from typing import List, Dict, Any
from datetime import datetime

DB_PATH = "chat.db"

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner TEXT NOT NULL,
  repo TEXT NOT NULL,
  pr INTEGER NOT NULL,
  author TEXT NOT NULL,
  role TEXT NOT NULL,   -- 'user' | 'system' | 'ai' | 'coderabbit'
  content TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_SQL)
        await db.commit()

async def append_message(owner: str, repo: str, pr: int, author: str, role: str, content: str) -> int:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO messages (owner, repo, pr, author, role, content, created_at) VALUES (?,?,?,?,?,?,?)",
            (owner, repo, pr, author, role, content, now),
        )
        await db.commit()
        return cur.lastrowid

async def list_messages(owner: str, repo: str, pr: int, limit: int = 200) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, owner, repo, pr, author, role, content, created_at "
            "FROM messages WHERE owner=? AND repo=? AND pr=? "
            "ORDER BY id ASC LIMIT ?",
            (owner, repo, pr, limit),
        )
        rows = await cur.fetchall()
    cols = ["id", "owner", "repo", "pr", "author", "role", "content", "created_at"]
    return [dict(zip(cols, r)) for r in rows]
