# status.py - одна команда: службы, аккаунты, цели, ответы, события
import os, sqlite3, subprocess

DB = os.getenv('HUNTER_DB', 'hunter.db')

def main():
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    q = lambda s: con.execute(s).fetchall()

    print('=== СЛУЖБЫ ===')
    for s in ['hunter.service', 'hunter-recv.service', 'hunter-worker.service', 'hunter-worker1.service']:
        r = subprocess.run(['systemctl', 'is-active', s], capture_output=True, text=True)
        print('%-24s %s' % (s, r.stdout.strip()))

    print()
    print('=== АККАУНТЫ ===')
    import guard
    for r in q("select name from accounts order by name"):
        print(guard.report(r['name']))

    print()
    print('=== ЦЕЛИ ===')
    for r in q("select status, count(*) c from hits group by status order by c desc"):
        print('%-8s %s' % (r['status'], r['c']))
    print('годных к отправке: %s' % q(
        "select count(*) c from hits where status='new' and username is not null "
        "and is_ad=0 and is_seller=0 and is_hr=0 and is_closed=0 and score>=6")[0]['c'])
    print('резерв в skip с юзернеймом: %s' % q(
        "select count(*) c from hits where status='skip' and username is not null "
        "and is_ad=0 and is_seller=0 and is_hr=0 and is_closed=0")[0]['c'])

    print()
    print('=== ОТВЕТЫ ===')
    print('всего: %s' % q("select count(*) c from replies")[0]['c'])
    for r in q("select username, text from replies order by id desc limit 5"):
        print('  @%s | %s' % (r['username'], (r['text'] or '').replace(chr(10), ' ')[:70]))

    print()
    print('=== СОБЫТИЯ (последние 10) ===')
    for r in q("select at, account, kind, detail from events order by id desc limit 10"):
        print('%s %s %-10s %s' % (r['at'][11:19], r['account'], r['kind'], (r['detail'] or '')[:40]))
    con.close()

main()
