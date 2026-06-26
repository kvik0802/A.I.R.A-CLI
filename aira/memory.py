"""
AIRA Memory Engine
------------------
Cross-session persistent memory with FTS, skill auto-creation,
session summarization, and project context awareness.
Beats Hermes: every memory is tagged with project, priority, and source agent.
"""

import json
import os
import sqlite3
import datetime
from pathlib import Path
from typing import Optional


AIRA_HOME = Path.home() / ".aira"
DB_PATH = AIRA_HOME / "memory.db"
SKILLS_PATH = AIRA_HOME / "skills"
SESSIONS_PATH = AIRA_HOME / "sessions"


def init_storage():
    AIRA_HOME.mkdir(exist_ok=True)
    SKILLS_PATH.mkdir(exist_ok=True)
    SESSIONS_PATH.mkdir(exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Check if old incompatible DB exists
    tables = [row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    needs_recreate = False
    if "memories" in tables:
        cols = {row[1] for row in c.execute("PRAGMA table_info(memories)").fetchall()}
        required = {"id", "content", "project", "tags", "priority", "source", "created_at", "accessed_at", "access_count"}
        if not required.issubset(cols):
            needs_recreate = True

    if needs_recreate:
        c.execute("DROP TABLE IF EXISTS memories")
        c.execute("DROP TABLE IF EXISTS memories_fts")

    c.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            project TEXT DEFAULT 'AIRA',
            tags TEXT DEFAULT '',
            priority INTEGER DEFAULT 1,
            source TEXT DEFAULT 'user',
            created_at TEXT NOT NULL,
            accessed_at TEXT NOT NULL,
            access_count INTEGER DEFAULT 0
        )
    """)

    try:
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
            USING fts5(content, project, tags, content='memories', content_rowid='id')
        """)
    except Exception:
        c.execute("DROP TABLE IF EXISTS memories_fts")
        c.execute("""
            CREATE VIRTUAL TABLE memories_fts
            USING fts5(content, project, tags, content='memories', content_rowid='id')
        """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            steps TEXT NOT NULL,
            use_count INTEGER DEFAULT 0,
            success_rate REAL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary TEXT,
            project TEXT DEFAULT 'AIRA',
            started_at TEXT NOT NULL,
            ended_at TEXT,
            message_count INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            name TEXT PRIMARY KEY,
            description TEXT,
            context TEXT,
            created_at TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )
    """)

    # ── Knowledge Graph ──
    c.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            relation TEXT NOT NULL,
            weight REAL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            UNIQUE(source_id, target_id, relation)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            node_type TEXT DEFAULT 'memory',
            metadata TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def _now():
    return datetime.datetime.now().isoformat()


# ── MEMORY ──────────────────────────────────────────────────────────────────

def save_memory(content: str, project: str = "AIRA", tags: list = None, priority: int = 1, source: str = "user"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    tags_str = ",".join(tags or [])
    now = _now()
    c.execute(
        "INSERT INTO memories (content, project, tags, priority, source, created_at, accessed_at) VALUES (?,?,?,?,?,?,?)",
        (content, project, tags_str, priority, source, now, now)
    )
    rowid = c.lastrowid
    try:
        c.execute("INSERT INTO memories_fts(rowid, content, project, tags) VALUES (?,?,?,?)",
                  (rowid, content, project, tags_str))
    except Exception:
        pass
    conn.commit()
    conn.close()

    # Auto-link to knowledge graph
    try:
        auto_link_memories(rowid, content, tags or [])
    except Exception:
        pass

    return rowid


def search_memory(query: str, project: str = None, limit: int = 10) -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if project:
        c.execute("""
            SELECT m.id, m.content, m.project, m.tags, m.priority, m.created_at
            FROM memories_fts fts
            JOIN memories m ON m.id = fts.rowid
            WHERE memories_fts MATCH ? AND m.project = ?
            ORDER BY m.priority DESC, m.access_count DESC
            LIMIT ?
        """, (query, project, limit))
    else:
        c.execute("""
            SELECT m.id, m.content, m.project, m.tags, m.priority, m.created_at
            FROM memories_fts fts
            JOIN memories m ON m.id = fts.rowid
            WHERE memories_fts MATCH ?
            ORDER BY m.priority DESC, m.access_count DESC
            LIMIT ?
        """, (query, limit))
    rows = c.fetchall()
    # Update access count
    if rows:
        ids = [r[0] for r in rows]
        c.executemany("UPDATE memories SET access_count = access_count+1, accessed_at=? WHERE id=?",
                      [(_now(), i) for i in ids])
        conn.commit()
    conn.close()
    return [{"id": r[0], "content": r[1], "project": r[2], "tags": r[3], "priority": r[4], "created_at": r[5]} for r in rows]


def get_all_memories(project: str = None, limit: int = 20) -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if project:
        c.execute("SELECT id, content, project, tags, priority, created_at FROM memories WHERE project=? ORDER BY priority DESC, accessed_at DESC LIMIT ?", (project, limit))
    else:
        c.execute("SELECT id, content, project, tags, priority, created_at FROM memories ORDER BY priority DESC, accessed_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "content": r[1], "project": r[2], "tags": r[3], "priority": r[4], "created_at": r[5]} for r in rows]


def delete_memory(memory_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM memories WHERE id=?", (memory_id,))
    c.execute("DELETE FROM memories_fts WHERE rowid=?", (memory_id,))
    conn.commit()
    conn.close()


# ── SKILLS ──────────────────────────────────────────────────────────────────

def save_skill(name: str, description: str, steps: list):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = _now()
    steps_json = json.dumps(steps)
    c.execute("""
        INSERT INTO skills (name, description, steps, created_at, updated_at)
        VALUES (?,?,?,?,?)
        ON CONFLICT(name) DO UPDATE SET
            description=excluded.description,
            steps=excluded.steps,
            updated_at=excluded.updated_at
    """, (name, description, steps_json, now, now))
    conn.commit()
    conn.close()


def get_skill(name: str) -> Optional[dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, description, steps, use_count, success_rate FROM skills WHERE name=?", (name,))
    row = c.fetchone()
    if row:
        c.execute("UPDATE skills SET use_count=use_count+1 WHERE name=?", (name,))
        conn.commit()
    conn.close()
    if not row:
        return None
    return {"name": row[0], "description": row[1], "steps": json.loads(row[2]), "use_count": row[3], "success_rate": row[4]}


def list_skills() -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, description, use_count, success_rate, updated_at FROM skills ORDER BY use_count DESC")
    rows = c.fetchall()
    conn.close()
    return [{"name": r[0], "description": r[1], "use_count": r[2], "success_rate": r[3], "updated_at": r[4]} for r in rows]


def update_skill_success(name: str, success: bool):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT success_rate, use_count FROM skills WHERE name=?", (name,))
    row = c.fetchone()
    if row:
        rate, count = row
        new_rate = ((rate * count) + (1 if success else 0)) / (count + 1)
        c.execute("UPDATE skills SET success_rate=? WHERE name=?", (new_rate, name))
        conn.commit()
    conn.close()


# ── SESSIONS ────────────────────────────────────────────────────────────────

def start_session(project: str = "AIRA") -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO sessions (project, started_at) VALUES (?,?)", (project, _now()))
    sid = c.lastrowid
    conn.commit()
    conn.close()
    return sid


def end_session(session_id: int, summary: str, message_count: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE sessions SET ended_at=?, summary=?, message_count=? WHERE id=?",
              (_now(), summary, message_count, session_id))
    conn.commit()
    conn.close()


def get_recent_sessions(limit: int = 5) -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, project, summary, started_at, message_count FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "project": r[1], "summary": r[2], "started_at": r[3], "message_count": r[4]} for r in rows]


# ── PROJECTS ────────────────────────────────────────────────────────────────

def save_project(name: str, description: str, context: str = ""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO projects (name, description, context, created_at)
        VALUES (?,?,?,?)
        ON CONFLICT(name) DO UPDATE SET description=excluded.description, context=excluded.context
    """, (name, description, context, _now()))
    conn.commit()
    conn.close()


def list_projects() -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, description, created_at, active FROM projects ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [{"name": r[0], "description": r[1], "created_at": r[2], "active": r[3]} for r in rows]


# ── CUSTOM AGENTS ───────────────────────────────────────────────────────────

AGENTS_DIR = AIRA_HOME / "agents"


def save_custom_agent(name: str, description: str, system_prompt: str, icon: str = "🤖"):
    """Save a custom agent definition."""
    AGENTS_DIR.mkdir(exist_ok=True)
    agent_file = AGENTS_DIR / f"{name}.json"
    data = {
        "name": name,
        "description": description,
        "system": system_prompt,
        "icon": icon,
        "custom": True,
    }
    with open(agent_file, "w") as f:
        json.dump(data, f, indent=2)
    return data


def get_custom_agent(name: str) -> Optional[dict]:
    """Load a custom agent by name."""
    agent_file = AGENTS_DIR / f"{name}.json"
    if agent_file.exists():
        try:
            with open(agent_file) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def list_custom_agents() -> list:
    """List all saved custom agents."""
    AGENTS_DIR.mkdir(exist_ok=True)
    agents = []
    for f in sorted(AGENTS_DIR.glob("*.json")):
        try:
            with open(f) as fh:
                agents.append(json.load(fh))
        except Exception:
            pass
    return agents


def delete_custom_agent(name: str) -> bool:
    """Delete a custom agent."""
    agent_file = AGENTS_DIR / f"{name}.json"
    if agent_file.exists():
        agent_file.unlink()
        return True
    return False


# ── KNOWLEDGE GRAPH ──────────────────────────────────────────────────────────


def add_knowledge_edge(source_id: int, target_id: int, relation: str, weight: float = 1.0):
    """Link two memories with a typed relation."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT OR REPLACE INTO knowledge_edges (source_id, target_id, relation, weight, created_at)
            VALUES (?,?,?,?,?)
        """, (source_id, target_id, relation, weight, _now()))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_linked_memories(memory_id: int, relation: str = None, max_depth: int = 2) -> list:
    """Walk the graph from a memory node, returning linked memories."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    visited = set()
    results = []

    def _walk(node_id, depth):
        if node_id in visited or depth > max_depth:
            return
        visited.add(node_id)
        if relation:
            rows = c.execute("""
                SELECT e.target_id, e.relation, e.weight, m.content, m.project
                FROM knowledge_edges e
                JOIN memories m ON m.id = e.target_id
                WHERE e.source_id = ? AND e.relation = ?
            """, (node_id, relation)).fetchall()
        else:
            rows = c.execute("""
                SELECT e.target_id, e.relation, e.weight, m.content, m.project
                FROM knowledge_edges e
                JOIN memories m ON m.id = e.target_id
                WHERE e.source_id = ?
            """, (node_id,)).fetchall()
        for target_id, rel, weight, content, project in rows:
            if target_id not in visited:
                results.append({"id": target_id, "relation": rel, "weight": weight, "content": content[:100], "project": project, "depth": depth})
                _walk(target_id, depth + 1)

    _walk(memory_id, 1)
    conn.close()
    return results


def graph_search(query: str, limit: int = 20) -> list:
    """Search memories and return them as graph nodes with their edges."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            SELECT m.id, m.content, m.project, m.tags, m.priority
            FROM memories_fts fts
            JOIN memories m ON m.id = fts.rowid
            WHERE memories_fts MATCH ?
            ORDER BY m.priority DESC
            LIMIT ?
        """, (query, limit))
    except Exception:
        c.execute("""
            SELECT id, content, project, tags, priority FROM memories
            WHERE content LIKE ? ORDER BY priority DESC LIMIT ?
        """, (f'%{query}%', limit))
    nodes = c.fetchall()
    result = []
    for n in nodes:
        edges = c.execute("""
            SELECT target_id, relation, weight FROM knowledge_edges WHERE source_id = ?
        """, (n[0],)).fetchall()
        result.append({
            "id": n[0], "content": n[1][:120], "project": n[2], "tags": n[3],
            "priority": n[4], "edges": [{"target": e[0], "relation": e[1], "weight": e[2]} for e in edges]
        })
    conn.close()
    return result


def auto_link_memories(memory_id: int, content: str, tags: list):
    """Automatically create edges between new memories and existing related ones."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Find memories with shared tags
    if tags:
        for tag in tags:
            rows = c.execute("""
                SELECT id FROM memories WHERE tags LIKE ? AND id != ? LIMIT 5
            """, (f'%{tag}%', memory_id)).fetchall()
            for row in rows:
                try:
                    c.execute("""
                        INSERT OR IGNORE INTO knowledge_edges (source_id, target_id, relation, weight, created_at)
                        VALUES (?,?,?,?,?)
                    """, (memory_id, row[0], f'shares_tag:{tag}', 0.5, _now()))
                except Exception:
                    pass
    conn.commit()
    conn.close()
