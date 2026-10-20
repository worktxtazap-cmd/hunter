# probe.py - разведка источников: тип, размер, вступили ли, отдаётся ли состав
import asyncio, os, sys
from dotenv import load_dotenv
from telethon import TelegramClient
from config import SOURCES
load_dotenv('.env')
S = os.getenv('SENDER_SESSION', 'sessions/sender')
c = TelegramClient(S, int(os.getenv('API_ID', '0')), os.getenv('API_HASH', ''))
A = int(sys.argv[1]) if len(sys.argv) > 1 else 0
B = int(sys.argv[2]) if len(sys.argv) > 2 else len(SOURCES)
async def main():
    await c.connect()
    print('сессия:', S, '| всего источников:', len(SOURCES))
    for ch in SOURCES[A:B]:
        try:
            e = await c.get_entity(ch)
        except Exception as ex:
            print(ch, 'ERR', str(ex)[:45]); continue
        left = getattr(e, 'left', False)
        n = 0
        if not left:
            try:
                async for u in c.iter_participants(e, limit=40):
                    n += 1
            except Exception as ex:
                n = 'ERR ' + str(ex)[:28]
        print('%-26s %-8s members=%-7s left=%-5s yield=%s' % (
            ch, type(e).__name__, getattr(e, 'participants_count', '?'), left, n))
    await c.disconnect()
asyncio.run(main())
