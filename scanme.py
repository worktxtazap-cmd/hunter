import asyncio, os
from dotenv import load_dotenv
from telethon import TelegramClient
load_dotenv('.env')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
KEYS = ['заявок', 'ником', 'автоответ', 'аудитор', 'заготовки', 'что искал']

async def one(s):
    c = TelegramClient(s, API_ID, API_HASH)
    try:
        await c.connect()
        if not await c.is_user_authorized():
            return
        n = 0
        cnt = {}
        ex = {}
        async for m in c.iter_messages('me', limit=1000):
            n += 1
            t = (m.message or '').lower()
            for k in KEYS:
                if k in t:
                    cnt[k] = cnt.get(k, 0) + 1
                    if k not in ex:
                        ex[k] = (m.id, (m.message or '').replace(chr(10), ' | ')[:80])
        print('===', s, 'total', n)
        for k in KEYS:
            if cnt.get(k):
                print('  ', k, cnt[k], 'ex:', ex[k])
    except Exception as e:
        print('ERR', s, e)
    finally:
        await c.disconnect()

async def main():
    for f in sorted(os.listdir('sessions')):
        if f.endswith('.session'):
            await one('sessions/' + f)

asyncio.run(main())
