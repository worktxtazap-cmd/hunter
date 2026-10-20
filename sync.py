# sync.py - закрывает петлю ручной отправки: помечает отправленное, ловит ответы, алертит
import asyncio, os, sqlite3, sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv('.env')
DB = os.getenv('HUNTER_DB', 'hunter.db')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')

ACC, SESSION = 'acc2', 'sessions/drafts2.session'
if '--account' in sys.argv:
    ACC = sys.argv[sys.argv.index('--account') + 1]
if '--session' in sys.argv:
    SESSION = sys.argv[sys.argv.index('--session') + 1]

def norm(s):
    return ' '.join((s or '').lower().split())

async def main():
    con = sqlite3.connect(DB, timeout=30)
    con.execute("create table if not exists replies (id integer primary key autoincrement, username text, msg_id integer, text text, at text, unique(username, msg_id))")
    con.commit()
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.connect()
    if not await c.is_user_authorized():
        print('NOT AUTHORIZED', SESSION); return

    drafts = con.execute("select id, username, text from hits where status='draft' and username is not null").fetchall()
    sent = 0
    for hid, u, txt in drafts:
        try:
            ent = await c.get_entity(u)
            head = norm(txt)[:30]
            for m in await c.get_messages(ent, limit=8):
                if m.out and norm(m.message)[:30] == head:
                    con.execute("update hits set status='sent', sent_at=?, sent_by='manual' where id=?",
                                (datetime.now(timezone.utc).isoformat(timespec='seconds'), hid))
                    con.commit(); sent += 1
                    print('отправлено вручную:', '@' + u)
                    break
        except Exception as e:
            print('draft fail', u, type(e).__name__, e)

    news = []
    for (u,) in con.execute("select distinct username from hits where sent_at is not null and username is not null"):
        try:
            ent = await c.get_entity(u)
            for m in await c.get_messages(ent, limit=5):
                if m.out or not m.message:
                    continue
                cur = con.execute("insert or ignore into replies (username, msg_id, text, at) values (?,?,?,?)",
                                  (u, m.id, m.message, datetime.now(timezone.utc).isoformat(timespec='seconds')))
                if cur.rowcount:
                    news.append((u, m.message))
        except Exception as e:
            print('read fail', u, type(e).__name__)
    con.commit()
    for u, t in news:
        print('ОТВЕТ', '@' + u, '|', t.replace(chr(10), ' ')[:120])
    if news:
        body = 'ОТВЕТЫ %s (%d):\n' % (ACC, len(news)) + '\n'.join(
            '@%s: %s' % (u, t.replace(chr(10), ' ')[:150]) for u, t in news[:10])
        try:
            await c.send_message('me', body)
        except Exception as e:
            print('алерт не ушёл', e)
    con.close()
    await c.disconnect()
    print('sync %s: помечено отправленными %d, новых ответов %d' % (ACC, sent, len(news)))

asyncio.run(main())
