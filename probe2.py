import asyncio, os
from dotenv import load_dotenv
from telethon import TelegramClient
load_dotenv('.env')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')

async def dump(s, tag):
    c = TelegramClient(s, API_ID, API_HASH)
    try:
        await c.connect()
        me = await c.get_me()
        print('===', tag, s, getattr(me, 'username', None))
        i = 0
        async for m in c.iter_messages('me', limit=300):
            i += 1
            t = (m.message or '').replace(chr(10), ' | ')
            print(i, m.id, repr(t[:110]))
        print('total', i)
    except Exception as e:
        print('ERR', s, e)
    finally:
        await c.disconnect()


async def main():
    await dump('sessions/drafts2.session', 'ACC2')
    await dump('sessions/sync1.session', 'ACC1')


asyncio.run(main())
