"""MCP server for managing notebooks and notes with tags and full-text search.

Storage is a single SQLite database using an FTS5 index over note titles,
content, and tags for the search tool. The database lives at $NOTEBOOK_DB if
set, otherwise ~/.notebook-mcp/notebook.db.

Run directly (stdio transport):
    python notebook_server.py
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(
    os.environ.get("NOTEBOOK_DB") or Path.home() / ".notebook-mcp" / "notebook.db"
)

mcp = FastMCP("notebook")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:  # commit on success, roll back on exception
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS notebooks (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY,
                notebook_id INTEGER NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_notes_notebook_id ON notes(notebook_id);

            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                title, content, tags,
                content='notes', content_rowid='id'
            );

            CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
                INSERT INTO notes_fts(rowid, title, content, tags)
                VALUES (new.id, new.title, new.content, new.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
                INSERT INTO notes_fts(notes_fts, rowid, title, content, tags)
                VALUES ('delete', old.id, old.title, old.content, old.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
                INSERT INTO notes_fts(notes_fts, rowid, title, content, tags)
                VALUES ('delete', old.id, old.title, old.content, old.tags);
                INSERT INTO notes_fts(rowid, title, content, tags)
                VALUES (new.id, new.title, new.content, new.tags);
            END;
            """
        )


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_tags(tags: list[str] | None) -> list[str]:
    return sorted({t.strip().lower() for t in (tags or []) if t.strip()})


def note_to_dict(row: sqlite3.Row, notebook_name: str | None = None) -> dict:
    d = {
        "id": row["id"],
        "notebook_id": row["notebook_id"],
        "title": row["title"],
        "content": row["content"],
        "tags": json.loads(row["tags"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if notebook_name is not None:
        d["notebook"] = notebook_name
    return d


@mcp.tool()
def create_notebook(name: str, description: str = "") -> str:
    """Create a new notebook to hold notes.

    Args:
        name: Unique name for the notebook.
        description: Optional description of what the notebook is for.
    """
    with get_db() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO notebooks (name, description, created_at) VALUES (?, ?, ?)",
                (name, description, now()),
            )
        except sqlite3.IntegrityError:
            raise ValueError(f"A notebook named '{name}' already exists.")
        new_id = cur.lastrowid
    return json.dumps({"id": new_id, "name": name, "description": description})


@mcp.tool()
def create_note(notebook: str, title: str, content: str, tags: list[str] | None = None) -> str:
    """Create a note inside a notebook.

    Args:
        notebook: Name of an existing notebook.
        title: Title of the note.
        content: Body of the note (markdown or plain text).
        tags: Optional list of tags, e.g. ["work", "ideas"].
    """
    tags = normalize_tags(tags)
    with get_db() as conn:
        nb = conn.execute("SELECT id FROM notebooks WHERE name = ?", (notebook,)).fetchone()
        if nb is None:
            raise ValueError(
                f"Notebook '{notebook}' not found. Create it first with create_notebook."
            )
        ts = now()
        cur = conn.execute(
            "INSERT INTO notes (notebook_id, title, content, tags, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (nb["id"], title, content, json.dumps(tags), ts, ts),
        )
        new_id = cur.lastrowid
    return json.dumps({"id": new_id, "notebook": notebook, "title": title, "tags": tags})


@mcp.tool()
def read_note(note_id: int) -> str:
    """Read a note by its id, returning title, content, tags, and timestamps.

    Args:
        note_id: The id of the note (as returned by create_note or search_notes).
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT notes.*, notebooks.name AS notebook_name FROM notes"
            " JOIN notebooks ON notebooks.id = notes.notebook_id WHERE notes.id = ?",
            (note_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"Note {note_id} not found.")
    return json.dumps(note_to_dict(row, row["notebook_name"]), indent=2)


@mcp.tool()
def update_note(
    note_id: int,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """Update a note's title, content, and/or tags. Only provided fields change.

    Args:
        note_id: The id of the note to update.
        title: New title (omit to keep current).
        content: New content, replaces the old content entirely (omit to keep current).
        tags: New full list of tags, replaces the old tags (omit to keep current).
    """
    if title is None and content is None and tags is None:
        raise ValueError("Provide at least one of title, content, or tags.")
    fields, values = [], []
    if title is not None:
        fields.append("title = ?")
        values.append(title)
    if content is not None:
        fields.append("content = ?")
        values.append(content)
    if tags is not None:
        fields.append("tags = ?")
        values.append(json.dumps(normalize_tags(tags)))
    fields.append("updated_at = ?")
    values.append(now())
    values.append(note_id)
    with get_db() as conn:
        cur = conn.execute(f"UPDATE notes SET {', '.join(fields)} WHERE id = ?", values)
        if cur.rowcount == 0:
            raise ValueError(f"Note {note_id} not found.")
    return read_note(note_id)


@mcp.tool()
def search_notes(
    query: str = "",
    notebook: str | None = None,
    tag: str | None = None,
    limit: int = 20,
) -> str:
    """Search notes by full-text query, notebook, and/or tag.

    Args:
        query: Full-text search over titles, content, and tags. Supports FTS5
            syntax (AND/OR/NOT, "exact phrases", prefix*); a query that is not
            valid FTS5 syntax is matched as literal words instead. Empty
            matches all notes.
        notebook: Restrict results to this notebook name.
        tag: Restrict results to notes carrying this exact tag.
        limit: Maximum number of results (default 20).
    """
    sql = (
        "SELECT notes.*, notebooks.name AS notebook_name FROM notes"
        " JOIN notebooks ON notebooks.id = notes.notebook_id"
    )
    where, params = [], []
    has_query = bool(query.strip())
    if has_query:
        sql += " JOIN notes_fts ON notes_fts.rowid = notes.id"
        where.append("notes_fts MATCH ?")
        params.append(query)
        order = "ORDER BY notes_fts.rank"
    else:
        order = "ORDER BY notes.updated_at DESC"
    if notebook:
        where.append("notebooks.name = ?")
        params.append(notebook)
    if tag:
        where.append("EXISTS (SELECT 1 FROM json_each(notes.tags) WHERE json_each.value = ?)")
        params.append(tag.strip().lower())
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" {order} LIMIT ?"
    params.append(max(1, limit))

    with get_db() as conn:
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            if not has_query:
                raise
            # Not valid FTS5 syntax (e.g. bare punctuation like e-mail or
            # O'Brien): quote each word and match the terms literally.
            params[0] = " ".join(
                '"{}"'.format(t.replace('"', '""')) for t in query.split()
            )
            rows = conn.execute(sql, params).fetchall()

    results = []
    for row in rows:
        note = note_to_dict(row, row["notebook_name"])
        # Trim content to a snippet so result lists stay readable.
        if len(note["content"]) > 200:
            note["content"] = note["content"][:200] + "…"
        results.append(note)
    return json.dumps({"count": len(results), "results": results}, indent=2)


init_db()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
