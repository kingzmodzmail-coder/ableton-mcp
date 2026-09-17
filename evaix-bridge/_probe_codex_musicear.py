import sqlite3
from pathlib import Path
base = Path(r"C:\Users\Gebruiker\.codex")
sess = base / "sessions"
print("sessions exists", sess.exists())
if sess.exists():
    files = [p for p in sess.rglob("*") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files[:40]:
        print(p, p.stat().st_size)

keys = ("music ear", "musicear", "disappear", "ableton", "astra", "stem", "warp")
for dbname in ["thread_history_1.sqlite", "state_5.sqlite", "logs_2.sqlite", "goals_1.sqlite"]:
    db = base / dbname
    if not db.exists():
        print("missing", dbname)
        continue
    print("===", dbname)
    con = sqlite3.connect(str(db))
    try:
        tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'").fetchall()]
        print("tables", tables[:40])
        for t in tables:
            cols = [r[1] for r in con.execute(f"pragma table_info({t})")]
            textcols = [c for c in cols if c and any(x in c.lower() for x in ("text", "content", "title", "summary", "prompt", "message", "body", "name"))]
            if not textcols:
                continue
            for c in textcols:
                try:
                    q = (
                        f"select rowid, substr({c},1,240) from {t} where "
                        + " or ".join([f"lower(ifnull({c},'')) like '%{k}%'" for k in keys])
                        + " limit 10"
                    )
                    rows = con.execute(q).fetchall()
                    for rowid, snippet in rows:
                        print("HIT", t, c, rowid, (snippet or "").replace("\n", " ")[:220])
                except Exception as e:
                    print("err", t, c, type(e).__name__, e)
    finally:
        con.close()

idx = base / "session_index.jsonl"
if idx.exists():
    print("=== session_index matches")
    for ln in idx.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]:
        low = ln.lower()
        if any(k in low for k in keys):
            print(ln[:320])
