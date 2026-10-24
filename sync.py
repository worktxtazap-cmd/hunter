# sync.py - помечает отправленное руками, ловит ответы и отвечает сам
import asyncio, fcntl, os, random, sqlite3, sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import ChatWriteForbiddenError, FloodWaitError, PeerFloodError

import templates

load_dotenv('.env')
DB = os.getenv('HUNTER_DB', 'hunter.db')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')

ACC, SESSION = 'acc2', 'sessions/drafts2.session'
if '--account' in sys.argv:
    ACC = sys.argv[sys.argv.index('--account') + 1]
if '--session' in sys.argv:
    SESSION = sys.argv[sys.argv.index('--session') + 1]

MAX_ANSWER = int(os.getenv('SYNC_MAX_ANSWER', '3'))
PRICE = ['сколько', 'цена', 'цену', 'стоит', 'прайс', 'стоимость']
YES = ['да', 'интересно', 'актуально', 'давай', 'нужно', 'надо', 'подходит']

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def norm(s):
    return ' '.join((s or '').lower().split())

def answer_for(t):
    low = (t or '').lower()
    if any(x in low for x in PRICE):
        return ('Здравствуйте! 1 чат - $5, 3 чата - $12, 10 чатов - $30. Входит: ник, id, имя, '
                'телефон где есть, боты и дубли вычищены, разбито по активности. Срок 1-3 часа. '
                'Демо: ' + templates.DEMO + ' Оплата USDT/TON или карта.')
    if any(x in low for x in YES):
        return ('Отлично! Скиньте название чата - соберу демо бесплатно за 1-3 часа, посмотрите. '
                'Пример базы: ' + templates.DEMO)
    return ('Здравствуйте! Я по базам и парсингу: соберу контакты из любого чата, чистка и сегмент '
            'по активности. 1 чат $5, 3 чата $12, 10 чатов $30. Демо: ' + templates.DEMO)

def only_one():
    f = open(SESSION + '.lock', 'w')
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print('другой sync уже держит', SESSION)
        return None
    f.write(str(os.getpid())); f.flush()
    return f

async def main():
    if only_one() is None:
        return
    con = sqlite3.connect(DB, timeout=30)
    con.execute("create table if not exists replies (id integer primary key autoincrement, username text, msg_id integer, text text, at text, unique(username, msg_id))")
    try:
        con.execute("alter table replies add column answered integer default 0")
    except Exception:
        pass
    con.commit()

    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.connect()
    if not await c.is_user_authorized():
        print('NOT AUTHORIZED', SESSION)
        return

    sent = 0
    for hid, u, txt in con.execute("select id, username, text from hits where status='draft' and username is not null").fetchall():
        try:
            ent = await c.get_entity(u)
            head = norm(txt)[:30]
            for m in await c.get_messages(ent, limit=8):
                if m.out and norm(m.message)[:30] == head:
                    con.execute("update hits set status='sent', sent_at=?, sent_by='manual' where id=?", (now_iso(), hid))
                    sent += 1
                    print('отправлено вручную:', '@' + u)
                    break
        except Exception as e:
            print('draft fail', u, type(e).__name__)
    con.commit()

    news = []
    for (u,) in con.execute("select distinct username from hits where sent_at is not null and username is not null").fetchall():
        try:
            ent = await c.get_entity(u)
            last = None
            for m in await c.get_messages(ent, limit=6):
                if m.out or not m.message:
                    continue
                last = m
                break
            if not last:
                continue
            cur = con.execute("insert or ignore into replies (username, msg_id, text, at) values (?,?,?,?)",
                              (u, last.id, last.message, now_iso()))
            if cur.rowcount:
                news.append((u, last.message, ent, last.id))
        except Exception as e:
            print('read fail', u, type(e).__name__)
    con.commit()

    replied = 0
    todo = con.execute("select username, max(msg_id), max(text) from replies where answered=0 group by username order by max(id) desc limit ?", (MAX_ANSWER,)).fetchall()
    for u, mid, t in todo:
        try:
            ent = await c.get_entity(u)
        except Exception:
            continue
        txt = answer_for(t)
        try:
            await c.send_message(ent, txt)
            con.execute("update replies set answered=1 where username=?", (u,))
            con.commit()
            replied += 1
            print('автоответ', '@' + u)
        except ChatWriteForbiddenError:
            print('ЛС закрыты', u)
        except FloodWaitError as e:
            print('flood', e.seconds)
            await asyncio.sleep(e.seconds + 60)
        except PeerFloodError:
            print('PEERFLOOD, автоответ отложен', u)
            break
        except Exception as e:
            print('автоответ fail', u, type(e).__name__, e)
        await asyncio.sleep(random.randint(30, 90))

    con.close()
    await c.disconnect()
    print('sync %s: помечено %d, новых ответов %d, автоответов %d' % (ACC, sent, len(news), replied))

asyncio.run(main())
