# findchats.py - глобальный поиск чатов-источников через Telegram
import asyncio, os, sys
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest

load_dotenv('.env')
API_ID = int(os.getenv('API_ID'))
H = os.getenv('API_HASH')
QUERIES = sys.argv[1:] or ['парсинг баз', 'рассылка телеграм', 'фриланс заказы', 'чат фрилансеров', 'заказы на парсинг']

async def main():
    c = TelegramClient('sessions/find', API_ID, H)
    await c.connect()
    seen = set()
    for q in QUERIES:
        try:
            res = await c(SearchRequest(q=q, limit=20))
        except Exception as e:
            print('fail', q, type(e).__name__, e)
            continue
        print('=== %s ===' % q)
        for ch in res.chats:
            u = getattr(ch, 'username', None)
            if not u or u in seen:
                continue
            seen.add(u)
            print('%-34s %6s  %s' % (u, getattr(ch, 'participants_count', 0) or 0, (ch.title or '')[:40]))
        await asyncio.sleep(2)
    await c.disconnect()
    print('всего ников:', len(seen))

asyncio.run(main())
