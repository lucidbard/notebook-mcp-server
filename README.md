# Notebook MCP Server

A simple [Model Context Protocol](https://modelcontextprotocol.io) server for
creating notebooks and notes with tags and full-text search. Notes are stored
in a single SQLite database with an FTS5 index for search — no external
services required.

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

## Quick start (no clone needed)

The only prerequisite is [`uv`](https://docs.astral.sh/uv/getting-started/installation/).
The commands below are copy-pasteable as-is — no paths to edit.

**Claude Code:**

```sh
claude mcp add notebook -- uvx --from git+https://github.com/lucidbard/notebook-mcp-server notebook-mcp
```

**Claude Desktop** — add to `claude_desktop_config.json`
(Settings → Developer → Edit Config), then restart the app:

```json
{
  "mcpServers": {
    "notebook": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/lucidbard/notebook-mcp-server", "notebook-mcp"]
    }
  }
}
```

### Try it

Ask your client something like:

> Create a notebook called "ideas", then save a note in it titled "Search UX"
> tagged `ux` and `search`, with a few thoughts on query autocomplete.

Then later:

> Search my notes for anything about autocomplete.

The model will call `create_notebook`, `create_note`, and `search_notes` for you.

## Where your notes live

All data is one SQLite file at `~/.notebook-mcp/notebook.db` (created on first
run). Back up that file to back up your notes; delete it to start fresh. Set
the `NOTEBOOK_DB` environment variable to use a different location — handy for
keeping separate databases per project.

## Installing from a clone

If you'd rather not run from GitHub directly (Python 3.10+ required):

```sh
git clone https://github.com/lucidbard/notebook-mcp-server.git
cd notebook-mcp-server
pip install .
claude mcp add notebook -- notebook-mcp
```

`pip install .` puts a `notebook-mcp` command on your PATH, so the client
config never needs a file path. (If you do point a client at the script
directly, use the **absolute** path to `notebook_server.py` — placeholder
paths like `/path/to/...` fail to connect, and Git Bash silently rewrites
them into `C:/Program Files/Git/...` on Windows.)

## Development

```sh
pip install -r requirements.txt
python notebook_server.py                    # run the server (MCP over stdio)
python test_fixes.py                         # tool, error-path, and search tests
python stdio_test.py                         # end-to-end test over MCP stdio
python stdio_test.py uvx --from . notebook-mcp   # same, against the packaged install
```

Both test scripts use a throwaway temporary database — they never touch
`~/.notebook-mcp/notebook.db`.
