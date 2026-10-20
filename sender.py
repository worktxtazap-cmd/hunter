import asyncio, os, sqlite3, sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError, PeerFloodError, ChatWriteForbiddenError

import templates

load_dotenv()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION = os.getenv('SENDER_SESSION', 'sessions/sender')
if '--session' in sys.argv:
    SESSION = sys.argv[sys.argv.index('--session') + 1]
if '--session' in sys.argv:
    SESSION = sys.argv[sys.argv.index('--session') + 1]
DB = 'hunter.db'
PAUSE = int(os.getenv('SEND_PAUSE', '60'))


def arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


LIMIT = int(arg('--limit', os.getenv('SEND_LIMIT', '8')))
MIN_SCORE = int(arg('--min-score', os.getenv('SEND_MIN_SCORE', '8')))

client = TelegramClient(SESSION, API_ID, API_HASH)


def targets():
    con = sqlite3.connect(DB, timeout=30)
    done = set(r[0].lower() for r in con.execute(
        "select username from hits where sent_at is not null and username is not null"))
    rows = con.execute(
        "select id, username, score, keyword, text, chat from hits "
        "where status='new' and username is not null and score>=? "
        "and is_ad=0 and is_seller=0 and is_hr=0 "
        "order by score desc, id desc", (MIN_SCORE,)).fetchall()
    con.close()
    seen_u, seen_t, out = set(done), set(), []
    for r in rows:
        u = r[1].lower()
        t = ' '.join((r[4] or '').lower().split())[:70]
        if u in seen_u or t in seen_t:
            continue
        seen_u.add(u)
        seen_t.add(t)
        out.append(r)
    return out[:LIMIT], len(done)


async def main():
    live = '--send' in sys.argv
    tg, n_done = targets()
    print('уже писали ранее:', n_done)
    print('к отправке:', len(tg))
    for i, (hid, u, sc, kw, txt, ch) in enumerate(tg, 1):
        print(i, '@' + u, sc, kw, '|', templates.pick(kw, txt, ch).replace('\n', ' ')[:95])
    if not live:
        print('холостой прогон, ничего не отправлено')
        return
    await client.connect()
    if not await client.is_user_authorized():
        print('NOT AUTHORIZED')
        return
    con = sqlite3.connect(DB, timeout=30)
    ok = 0
    for i, (hid, u, sc, kw, txt, ch) in enumerate(tg, 1):
        try:
            await client.send_message(u, templates.pick(kw, txt, ch))
            con.execute("update hits set status='sent', sent_at=? where id=?",
                        (datetime.now(timezone.utc).isoformat(timespec='seconds'), hid))
            con.commit()
            ok += 1
            print('ok', i, '@' + u, flush=True)
        except ChatWriteForbiddenError:
            con.execute("update hits set status='skip' where id=?", (hid,))
            con.commit()
            print('ЛС закрыты', i, '@' + u, flush=True)
        except PeerFloodError:
            print('PEERFLOOD, пропуск', i, '@' + u, flush=True)
            await asyncio.sleep(90)
            continue
        except FloodWaitError as e:
            print('flood', e.seconds, flush=True)
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print('fail', i, '@' + u, type(e).__name__, e, flush=True)
        await asyncio.sleep(PAUSE)
    con.close()
    print('отправлено:', ok)


asyncio.run(main())
