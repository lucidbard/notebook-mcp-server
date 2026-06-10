import json
import os

import notebook_server as ns

ns.create_notebook("work", "Work notes")

# Errors now raise instead of returning strings
for fn, kwargs in [
    (ns.create_notebook, {"name": "work"}),
    (ns.create_note, {"notebook": "missing", "title": "x", "content": "y"}),
    (ns.read_note, {"note_id": 999}),
    (ns.update_note, {"note_id": 999}),
    (ns.update_note, {"note_id": 999, "title": "t"}),
]:
    try:
        fn(**kwargs)
        raise AssertionError(f"{fn.__name__}({kwargs}) did not raise")
    except ValueError as e:
        print(f"ok: {fn.__name__} raised: {e}")

# Tag search must find an old tagged note buried under newer untagged ones
ns.create_note("work", "Rare note", "The buried treasure.", ["rare"])
for i in range(30):
    ns.create_note("work", f"Filler {i}", "Nothing to see.", ["common"])
res = json.loads(ns.search_notes(tag="rare", limit=3))
assert res["count"] == 1 and res["results"][0]["title"] == "Rare note", res
print("ok: tag filter finds note outside the old limit*5 window")

# Tag filter combined with FTS query
res = json.loads(ns.search_notes(query="buried", tag="rare"))
assert res["count"] == 1, res
res = json.loads(ns.search_notes(query="buried", tag="common"))
assert res["count"] == 0, res
print("ok: tag filter composes with FTS query in SQL")

# Punctuated queries fall back to literal matching instead of erroring
ns.create_note("work", "Contacts", "Ask O'Brien to check the e-mail setup.", [])
for q in ["O'Brien", "e-mail", "e-mail setup"]:
    res = json.loads(ns.search_notes(q))
    assert res["count"] == 1, (q, res)
print("ok: punctuated queries (O'Brien, e-mail) match via literal fallback")

# Valid FTS5 syntax still works
res = json.loads(ns.search_notes('"buried treasure" OR fill*'))
assert res["count"] >= 2, res
print("ok: FTS5 operator syntax still works")

# Connections are closed: the db file must be deletable while module is loaded
del res
os.remove(ns.DB_PATH)
print("ok: notebook.db deletable -> no leaked open connections (Windows)")
