# saved.py - последние сообщения в Избранном, что видит юзер
import asyncio, os, sys
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv('.env')
API_ID = int(os.getenv('API_ID', '0'))
H = os.getenv('API_HASH', '')
n = 12
if '--n' in sys.argv:
    n = int(sys.argv[sys.argv.index('--n') + 1])

async def one(acc, sess):
    c = TelegramClient(sess, API_ID, H)
    await c.connect()
    if not await c.is_user_authorized():
        print('=====', acc, 'NOT AUTHORIZED'); return
    print('=====', acc, '=====')
    for m in await c.get_messages('me', limit=n):
        print(m.id, m.date.strftime('%H:%M'), (m.message or '').replace(chr(10), ' | ')[:110])
    await c.disconnect()

async def main():
    for a, s in (('acc1', 'sessions/drafts1.session'), ('acc2', 'sessions/drafts2.session')):
        await one(a, s)

asyncio.run(main())
