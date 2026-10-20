import sqlite3
c = sqlite3.connect("hunter.db")
for s, u, n, t in c.execute("select max(score), username, count(*), substr(text,1,100) from hits where status='new' and username is not null group by user_id order by max(score) desc limit 25"):
    print(s, u, "x" + str(n), "|", t.replace(chr(10), " "))
print("hot_users:", c.execute("select count(distinct user_id) from hits where status='new'").fetchone()[0])
