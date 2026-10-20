# worker.py - один процесс на аккаунт: читает ответы + шлёт пачки. Запуск через systemd.
import asyncio, fcntl, os, sqlite3, sys, time
from datetime import datetime, timezone

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import ChatWriteForbiddenError, FloodWaitError, PeerFloodError

import guard, templates

load_dotenv()

DB = os.getenv('HUNTER_DB', 'hunter.db')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION = os.getenv('WORKER_SESSION', 'sessions/sender2')
ACCOUNT = os.getenv('WORKER_ACCOUNT', 'acc2')
ALERT_PEER = os.getenv('ALERT_PEER', 'me')
BATCH = int(os.getenv('WORKER_BATCH', '5'))
ALERT_EVERY = int(os.getenv('ALERT_EVERY', '21600'))
MIN_SCORE = int(os.getenv('SEND_MIN_SCORE', '8'))

if '--session' in sys.argv:
    SESSION = sys.argv[sys.argv.index('--session') + 1]
if '--account' in sys.argv:
    ACCOUNT = sys.argv[sys.argv.index('--account') + 1]

def ts():
    return datetime.now().strftime('%H:%M:%S')

def log(*a):
    print(ts(), *a, flush=True)

def only_one():
    f = open(SESSION + '.lock', 'w')
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log('другой worker уже держит', SESSION)
        return None
    f.write(str(os.getpid())); f.flush()
    return f

def targets(con):
    done = set(r[0].lower() for r in con.execute(
        "select username from hits where sent_at is not null and username is not null"))
    rows = con.execute(
        "select id, username, score, keyword, text, chat from hits "
        "where status='new' and username is not null and score>=? "
        "and is_ad=0 and is_seller=0 and is_hr=0 "
        "order by score desc, id desc", (MIN_SCORE,)).fetchall()
    seen_u, seen_t, out = set(done), set(), []
    for r in rows:
        u = r[1].lower()
        t = ' '.join((r[4] or '').lower().split())[:70]
        if u in seen_u or t in seen_t:
            continue
        seen_u.add(u); seen_t.add(t); out.append(r)
    return out

async def read_replies(client, con):
    n = 0
    for d in await client.get_dialogs(limit=200):
        if not d.is_user:
            continue
        u = getattr(d.entity, 'username', None)
        if not u:
            continue
        if not con.execute("select 1 from hits where username=? and status='sent' limit 1", (u,)).fetchone():
            continue
        for m in await client.get_messages(d.entity, limit=6):
            if m.out or not m.message:
                continue
            cur = con.execute("insert or ignore into replies (username, msg_id, text, at) values (?,?,?,?)",
                              (u, m.id, m.message, datetime.now(timezone.utc).isoformat(timespec='seconds')))
            if cur.rowcount:
                n += 1
                log('ОТВЕТ', '@' + u, '|', m.message.replace(chr(10), ' ')[:160])
    con.commit()
    return n

async def send_batch(client, con, q):
    tg = targets(con)[:min(BATCH, q)]
    if not tg:
        return 0, 0
    ok = 0
    for i, (hid, u, sc, kw, txt, ch) in enumerate(tg, 1):
        if guard.quota(ACCOUNT) <= 0:
            break
        try:
            await client.send_message(u, templates.pick(kw, txt, ch))
            con.execute("update hits set status='sent', sent_at=?, sent_by=? where id=?",
                        (datetime.now(timezone.utc).isoformat(timespec='seconds'), ACCOUNT, hid))
            con.commit()
            guard.bump_sent(ACCOUNT)
            ok += 1
            log('ok', i, '@' + u, sc, kw)
        except ChatWriteForbiddenError:
            con.execute("update hits set status='skip' where id=?", (hid,)); con.commit()
            log('ЛС закрыты', i, '@' + u)
        except PeerFloodError:
            lvl = guard.pf_level(ACCOUNT) + 1
            secs = min(86400, 7200 * (2 ** (lvl - 1)))
            guard.set_cooldown(ACCOUNT, secs, 'PeerFlood уровень %d' % lvl)
            guard.event(ACCOUNT, 'peerflood', '@' + u)
            log('PEERFLOOD -> кулдаун %d ч (уровень %d)' % (secs // 3600, lvl))
            await alert(client, 'HUNTER %s: PeerFlood, пауза %d ч' % (ACCOUNT, secs // 3600))
            break
        except FloodWaitError as e:
            guard.event(ACCOUNT, 'flood', str(e.seconds))
            log('flood', e.seconds, 'с, спим')
            await asyncio.sleep(e.seconds + 60)
        except Exception as e:
            st = guard.bump_error(ACCOUNT, 'fail', '%s %s' % (type(e).__name__, e))
            log('fail', i, '@' + u, type(e).__name__, e, 'подряд:', st)
            if st >= 3:
                guard.set_cooldown(ACCOUNT, 3600, '3 ошибки подряд')
                log('3 ошибки -> пауза час')
                await alert(client, 'HUNTER %s: 3 ошибки подряд, пауза час' % ACCOUNT)
                break
        p = guard.sleep_pause()
        log('пауза', p, 'с')
        await asyncio.sleep(p)
    return ok, len(tg)

async def alert(client, text):
    try:
        await client.send_message(ALERT_PEER, text)
    except Exception as e:
        log('алерт не ушёл', type(e).__name__, e)

async def main():
    if only_one() is None:
        return
    guard.init()
    guard.ensure(ACCOUNT, SESSION)
    con = sqlite3.connect(DB, timeout=30)
    con.execute("create table if not exists replies (id integer primary key autoincrement, username text, msg_id integer, text text, at text, unique(username, msg_id))")
    con.commit()

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        log('NOT AUTHORIZED', SESSION)
        guard.event(ACCOUNT, 'noauth', SESSION)
        return
    me = await client.get_me()
    log('старт', ACCOUNT, '@' + (me.username or str(me.id)))
    guard.event(ACCOUNT, 'start', 'pid %s' % os.getpid())
    await alert(client, 'HUNTER старт %s' % ACCOUNT)

    last_alert = time.time()
    while True:
        try:
            if not guard.in_window():
                log('вне окна 09-21, спим 10 мин')
                await asyncio.sleep(600); continue
            cd = guard.cooldown_left(ACCOUNT)
            if cd > 0:
                log('кулдаун', cd, 'с')
                await asyncio.sleep(min(cd, 600)); continue
            if guard.quota(ACCOUNT) <= 0:
                log('лимит на сегодня выбран, спим 15 мин')
                await asyncio.sleep(900); continue

            n = await read_replies(client, con)
            if n:
                log('новых ответов:', n)

            ok, tried = await send_batch(client, con, guard.quota(ACCOUNT))
            if tried:
                log('пачка:', ok, 'из', tried, '|', guard.report(ACCOUNT))
                bp = guard.sleep_batch()
                log('перерыв', bp // 60, 'мин')
                await asyncio.sleep(bp)
            else:
                log('нет целей, спим 15 мин')
                await asyncio.sleep(900)

            if time.time() - last_alert > ALERT_EVERY:
                last_alert = time.time()
                await alert(client, 'HUNTER %s: %s' % (ACCOUNT, guard.report(ACCOUNT)))
        except Exception as e:
            log('цикл упал', type(e).__name__, e)
            guard.bump_error(ACCOUNT, 'cycle', str(e))
            await asyncio.sleep(120)

asyncio.run(main())
