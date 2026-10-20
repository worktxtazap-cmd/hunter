# guard.py - лимиты, рабочее окно, кулдауны, журнал. Общий модуль для worker.py
import os, random, sqlite3
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    KYIV = ZoneInfo('Europe/Kyiv')
except Exception:
    KYIV = timezone(timedelta(hours=3))

DB = os.getenv('HUNTER_DB', 'hunter.db')
WORK_FROM, WORK_TO = 9, 21          # окно по Киеву
BASE_LIMIT, STEP, MAX_LIMIT = 10, 5, 40
PAUSE_MIN, PAUSE_MAX = 120, 240      # между сообщениями
BATCH_MIN, BATCH_MAX = 480, 720     # после пачки

def conn():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c

def init():
    con = conn()
    con.execute("create table if not exists accounts ("
                "name text primary key, session text, enabled integer default 1, "
                "limit_today integer default 15, sent_today integer default 0, day text, "
                "cooldown_until text, err_streak integer default 0, "
                "status text default 'ok', note text, last_seen text)")
    con.execute("create table if not exists events (id integer primary key autoincrement, "
                "at text, account text, kind text, detail text)")
    con.commit(); con.close()

def now():
    return datetime.now(timezone.utc)

def today():
    return datetime.now(KYIV).strftime('%Y-%m-%d')

def event(account, kind, detail=''):
    con = conn()
    con.execute("insert into events (at, account, kind, detail) values (?,?,?,?)",
                (now().isoformat(timespec='seconds'), account, kind, str(detail)[:400]))
    con.commit(); con.close()

def ensure(name, session):
    init()
    con = conn()
    con.execute("insert or ignore into accounts (name, session, day, last_seen) values (?,?,?,?)",
                (name, session, today(), now().isoformat(timespec='seconds')))
    con.commit(); con.close()
    rollover(name)

def rollover(name):
    con = conn()
    r = con.execute("select day, limit_today from accounts where name=?", (name,)).fetchone()
    if r and r['day'] != today():
        lim = min(MAX_LIMIT, (r['limit_today'] or BASE_LIMIT) + STEP)
        con.execute("update accounts set day=?, limit_today=?, sent_today=0, err_streak=0 where name=?",
                    (today(), lim, name))
        con.commit()
        event(name, 'rollover', 'лимит на сегодня %d' % lim)
    con.close()

def row(name):
    con = conn()
    r = con.execute("select * from accounts where name=?", (name,)).fetchone()
    con.close()
    return r

def quota(name):
    rollover(name)
    r = row(name)
    if not r or not r['enabled']:
        return 0
    return max(0, (r['limit_today'] or 0) - (r['sent_today'] or 0))

def in_window():
    t = datetime.now(KYIV)
    return WORK_FROM <= t.hour < WORK_TO

def cooldown_left(name):
    r = row(name)
    if not r or not r['cooldown_until']:
        return 0
    try:
        d = datetime.fromisoformat(r['cooldown_until']) - now()
    except Exception:
        return 0
    return max(0, int(d.total_seconds()))

def set_cooldown(name, seconds, reason):
    until = (now() + timedelta(seconds=int(seconds))).isoformat(timespec='seconds')
    con = conn()
    con.execute("update accounts set cooldown_until=?, note=? where name=?", (until, reason, name))
    con.commit(); con.close()
    event(name, 'cooldown', '%s %sс, до %s' % (reason, seconds, until))

def bump_sent(name, n=1):
    con = conn()
    con.execute("update accounts set sent_today = sent_today + ?, err_streak = 0, last_seen = ? where name=?",
                (n, now().isoformat(timespec='seconds'), name))
    con.commit(); con.close()

def bump_error(name, kind, detail=''):
    con = conn()
    con.execute("update accounts set err_streak = err_streak + 1 where name=?", (name,))
    con.commit(); con.close()
    event(name, kind, detail)
    r = row(name)
    return r['err_streak'] if r else 1

def reset_errors(name):
    con = conn()
    con.execute("update accounts set err_streak = 0 where name=?", (name,))
    con.commit(); con.close()

def sleep_pause():
    return random.randint(PAUSE_MIN, PAUSE_MAX)

def sleep_batch():
    return random.randint(BATCH_MIN, BATCH_MAX)

def report(name):
    r = row(name)
    if not r:
        return 'нет аккаунта %s' % name
    return ('%s: лимит %s/%s, кулдаун %sс, ошибок подряд %s, статус %s'
            % (name, r['sent_today'], r['limit_today'], cooldown_left(name), r['err_streak'], r['status']))

if __name__ == '__main__':
    init()
    con = conn()
    for r in con.execute("select name from accounts order by name"):
        print(report(r['name']))
    con.close()

def pf_level(name, days=7):
    con = conn()
    r = con.execute("select count(*) from events where account=? and kind='peerflood' and at > ?",
                    (name, (now() - timedelta(days=days)).isoformat(timespec='seconds'))).fetchone()
    con.close()
    return r[0] if r else 0
