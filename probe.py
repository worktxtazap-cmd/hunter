import asyncio, os
from dotenv import load_dotenv
from telethon import TelegramClient
load_dotenv('.env')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESS = []
for f in sorted(os.listdir('sessions')):
    if f.endswith('.session'):
        SESS.append('sessions/' + f)

async def one(s):
    c = TelegramClient(s, API_ID, API_HASH)
    try:
        await c.connect()
        if not await c.is_user_authorized():
            print(s, 'NOT AUTHORIZED'); return
        me = await c.get_me()
        n = 0
        sample = []
        async for m in c.iter_messages('me', limit=300):
            n += 1
            if len(sample) < 8:
                t = (m.message or '').replace(chr(10), ' / ')
                sample.append(t[:70])
        print('===', s, 'user=', getattr(me, 'username', None), 'id=', getattr(me, 'id', None), 'me_msgs=', n)
        for x in sample:
            print('   >', x)
    except Exception as e:
        print('===', s, 'ERR', e)
    finally:
        await c.disconnect()


async def main():
    for s in SESS:
        await one(s)


asyncio.run(main())
