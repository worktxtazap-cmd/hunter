# drafts.py - zagotovki dlya otpravki s telefona
import asyncio, os, sqlite3, sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from telethon import TelegramClient

import templates
from telethon.errors import FloodWaitError

load_dotenv('.env')
DB = os.getenv('HUNTER_DB', 'hunter.db')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
MIN_SCORE = int(os.getenv('SEND_MIN_SCORE', '7'))

async def say(c, txt):
    for _ in range(5):
        try:
            return await c.send_message('me', txt)
        except FloodWaitError as e:
            print('wait', e.seconds); await asyncio.sleep(e.seconds + 3)

ACC, SESSION, n, mode, args = 'acc2', 'sessions/drafts2.session', 10, 'make', []
both = False
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == '--account' and i + 1 < len(sys.argv):
        ACC = sys.argv[i + 1]; i += 2; continue
    if a == '--session' and i + 1 < len(sys.argv):
        SESSION = sys.argv[i + 1]; i += 2; continue
    if a == '--n' and i + 1 < len(sys.argv):
        n = int(sys.argv[i + 1]); i += 2; continue
    if a == '--both':
        both = True; i += 1; continue
    if a in ('--list', '--sent', '--sent-all', '--back', '--wipe'):
        mode = a[2:]; i += 1; continue
    args.append(a); i += 1

def pick(con, k):
    done = set(r[0].lower() for r in con.execute("select username from hits where sent_at is not null and username is not null"))
    draft = set(r[0].lower() for r in con.execute("select username from hits where status='draft' and username is not null"))
    hot = set(r[0].lower() for r in con.execute("select username from hits where status='hot' and username is not null"))
    rows = con.execute(
        "select id, username, score, keyword, text, chat from hits "
        "where status='new' and username is not null and score>=? "
        "and is_ad=0 and is_seller=0 and is_hr=0 and is_closed=0 "
        "order by score desc, id desc", (MIN_SCORE,)).fetchall()
    out, seen_t, seen_u = [], set(), set()
    for r in rows:
        u = r[1].lower()
        t = ' '.join((r[4] or '').lower().split())[:70]
        if u in done or u in draft or u in hot or u in seen_u or t in seen_t:
            continue
        seen_t.add(t)
        seen_u.add(u)
        out.append(r)
    return out[:k]

def text_of(r):
    return templates.pick(r[3], r[4], r[5]).strip()

async def make(con):
    pend = con.execute("select count(*) from hits where status='draft'").fetchone()[0]
    room = int(os.getenv('DRAFTS_MAX_PEND', '40')) - pend
    if room <= 0:
        print('drafts pending', pend, 'enough'); return
    tg = pick(con, min(n, room))
    if not tg:
        print('no targets')
        return
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.connect()
    if not await c.is_user_authorized():
        print('NOT AUTHORIZED', SESSION); return
    await c.send_message('me', 'ЗАГОТОВКИ %s, %d шт. тапни ник, скопируй текст ниже' % (ACC, len(tg)))
    for j2, r in enumerate(tg, 1):
        hid, u, sc, kw, txt, ch = r
        body = '@%s\n\n%s\n\n%s' % (u, text_of(r), templates.LINK)
        await say(c, body)
        await asyncio.sleep(2)
        con.execute("update hits set status='draft' where id=?", (hid,))
        print(j2, '@' + u, sc, kw)
    con.commit()
    await c.disconnect()
    print('done drafts', len(tg))

PAT = ('заготовки', 'привет! видел ваш пост', 'делаю телеграм-ботов', 'пример, как выглядит база', 'новых заявок', 'с ником', 'ответы в чаты', 'что искал')

WIPE_SESSIONS = ('sessions/login.session', 'sessions/drafts1.session', 'sessions/drafts2.session', 'sessions/hot.session')

async def wipe(con):
    total = 0
    for s in WIPE_SESSIONS:
        if not os.path.exists(s):
            continue
        c = TelegramClient(s, API_ID, API_HASH)
        try:
            await c.connect()
            if not await c.is_user_authorized():
                print('not authorized', s); continue
            ids = []
            async for m in c.iter_messages('me', limit=600):
                t = (m.message or '').lower()
                if not t:
                    continue
                head = t.split('.')[0]
                if any(p in t for p in PAT) or (head.isdigit() and '@' in t[:45]):
                    ids.append(m.id)
            if ids:
                await c.delete_messages('me', ids)
            total += len(ids)
            print(s, 'deleted', len(ids))
        except Exception as e:
            print(s, 'error', e)
        finally:
            await c.disconnect()
    con.execute("update hits set status='new' where status in ('draft','hot')")
    con.commit()
    print('total deleted', total)

def show(con):
    for r in con.execute("select id, username, score from hits where status='draft' and username is not null order by id"):
        print(r[0], '@' + r[1], r[2])
    print('total drafts', con.execute("select count(*) from hits where status='draft' and username is not null").fetchone()[0])

def mark(con, users, status, sent):
    us = [u.lower().lstrip('@') for u in users]
    if not us:
        us = [r[0].lower() for r in con.execute("select username from hits where status='draft' and username is not null")]
    for u in us:
        con.execute("update hits set status=?, sent_at=?, sent_by=? where lower(username)=?", (status, sent, 'manual', u))
    con.commit()
    print('marked', status, len(us))

def main():
    con = sqlite3.connect(DB, timeout=30)
    if mode == 'wipe':
        asyncio.run(wipe(con))
    elif mode == 'list':
        show(con)
    elif mode == 'sent':
        mark(con, args, 'sent', datetime.now(timezone.utc).isoformat(timespec='seconds'))
    elif mode == 'sent-all':
        mark(con, [], 'sent', datetime.now(timezone.utc).isoformat(timespec='seconds'))
    elif mode == 'back':
        mark(con, args, 'new', None)
    elif both:
        for a, ss in (('acc1', 'sessions/drafts1.session'), ('acc2', 'sessions/drafts2.session')):
            globals()['ACC'] = a
            globals()['SESSION'] = ss
            asyncio.run(make(con))
    else:
        asyncio.run(make(con))
    con.close()

main()
