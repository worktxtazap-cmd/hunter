import asyncio
import os
import sqlite3
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION = os.getenv('SENDER_SESSION', 'sessions/sender')
if '--session' in sys.argv:
    SESSION = sys.argv[sys.argv.index('--session') + 1]
if '--session' in sys.argv:
    SESSION = sys.argv[sys.argv.index('--session') + 1]
DB = 'hunter.db'

client = TelegramClient(SESSION, API_ID, API_HASH)


async def main():
    await client.connect()
    if not await client.is_user_authorized():
        print('NOT AUTHORIZED')
        return
    con = sqlite3.connect(DB, timeout=30)
    con.execute('create table if not exists replies (id integer primary key autoincrement, username text, msg_id integer, text text, at text, unique(username, msg_id))')
    con.commit()
    n = 0
    for d in await client.get_dialogs(limit=200):
        if not d.is_user:
            continue
        u = getattr(d.entity, 'username', None)
        if not u:
            continue
        if not con.execute('select 1 from hits where username=? and status=? limit 1', (u, 'sent')).fetchone():
            continue
        for m in await client.get_messages(d.entity, limit=6):
            if m.out or not m.message:
                continue
            cur = con.execute('insert or ignore into replies (username, msg_id, text, at) values (?,?,?,?)', (u, m.id, m.message, datetime.now(timezone.utc).isoformat(timespec='seconds')))
            if cur.rowcount:
                n += 1
                print('NEW', u, '|', m.message.replace(chr(10), ' ')[:160])
    con.commit()
    con.close()
    print('новых ответов:', n)
    await client.disconnect()


asyncio.run(main())
