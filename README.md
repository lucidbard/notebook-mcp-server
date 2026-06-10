# Notebook MCP Server

A simple [Model Context Protocol](https://modelcontextprotocol.io) server for
creating notebooks and notes with tags and full-text search. Notes are stored in
a single SQLite database (`notebook.db`, created automatically next to the
script) with an FTS5 index for search — no external services required.

## Tools

| Tool | Description |
|---|---|
| `create_notebook` | Create a notebook (`name`, optional `description`). |
| `create_note` | Add a note to a notebook (`notebook`, `title`, `content`, optional `tags`). |
| `read_note` | Read a full note by `note_id`. |
| `update_note` | Update a note's `title`, `content`, and/or `tags` (only provided fields change). |
| `search_notes` | Full-text search over titles, content, and tags; filter by `notebook` and/or `tag`. Supports FTS5 syntax (`AND`, `OR`, `NOT`, `"exact phrase"`, `prefix*`); queries that aren't valid FTS5 syntax (e.g. `e-mail`) are matched as literal words instead. |

Errors (duplicate notebook, missing note, invalid arguments) are raised as
exceptions, so MCP clients receive them as proper tool errors (`isError`), not
as text that looks like a successful result.

## Getting started

### 1. Prerequisites

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/) or `pip`

### 2. Install

```sh
git clone https://github.com/lucidbard/notebook-mcp-server.git
cd notebook-mcp-server
pip install -r requirements.txt
```

### 3. Connect a client

**Claude Code** (CLI):

```sh
claude mcp add notebook -- python /path/to/notebook-mcp-server/notebook_server.py
```

**Claude Desktop** — add to `claude_desktop_config.json`
(Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "notebook": {
      "command": "python",
      "args": ["/path/to/notebook-mcp-server/notebook_server.py"]
    }
  }
}
```

On Windows, use a full path like `C:\\path\\to\\notebook-mcp-server\\notebook_server.py`.

### 4. Try it

Ask your client something like:

> Create a notebook called "ideas", then save a note in it titled "Search UX"
> tagged `ux` and `search`, with a few thoughts on query autocomplete.

Then later:

> Search my notes for anything about autocomplete.

The model will call `create_notebook`, `create_note`, and `search_notes` for
you. All data lives in `notebook.db` next to the server script — back it up or
delete it to start fresh.

### Run the server manually

```sh
python notebook_server.py   # speaks MCP over stdio
```

### Run the tests

```sh
python test_fixes.py   # exercises tools, error paths, and search edge cases
python stdio_test.py   # end-to-end check over MCP stdio transport
```

Both print `ok:`/`True` lines and exit silently on success; `test_fixes.py`
removes its test database when done.
