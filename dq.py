import sqlite3, sys
con = sqlite3.connect('/home/ubuntu/hunter/hunter.db', timeout=30)
cur = con.execute(sys.argv[1])
if cur.description:
    print(' | '.join(d[0] for d in cur.description))
    for r in cur.fetchall():
        print(' | '.join('' if v is None else str(v).replace(chr(10), ' ')[:110] for v in r))
con.commit()
con.close()
