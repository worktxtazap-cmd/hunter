import sqlite3
c = sqlite3.connect("hunter.db")
pat = ["парс","баз","выгрузк","скрап","сборщик"]
rows = c.execute("select max(score), username, count(*), text from hits where status='new' and username is not null group by user_id order by max(score) desc").fetchall()
out = [r for r in rows if any(p in r[3].lower() for p in pat)]
for s,u,n,t in out[:30]:
    print(s, u, "x"+str(n), "|", t.replace(chr(10)," ")[:110])
print("targets:", len(out))
