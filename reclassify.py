import sqlite3
from hunter import evaluate

con = sqlite3.connect("hunter.db", timeout=30)
rows = con.execute("select id, text from hits").fetchall()
keep = 0
drop = 0
for i, t in rows:
    ev = evaluate(t or "")
    if ev:
        con.execute("update hits set keyword=?, score=?, status='new' where id=?", (ev[0], ev[1], i))
        keep += 1
    else:
        con.execute("update hits set score=0, status='skip' where id=?", (i,))
        drop += 1
con.commit()
print("осталось:", keep, "отсеяно:", drop)
for kw, n in con.execute("select keyword, count(*) from hits where status='new' group by keyword order by 2 desc").fetchall():
    print("  ", kw, n)
print("--- топ заявок ---")
for u, s, t in con.execute("select username, score, substr(text,1,150) from hits where status='new' and username is not null order by score desc limit 12").fetchall():
    print(s, u, "|", t.replace("\n", " "))
con.close()
