# probe2.py - размер, скрыт ли состав, есть ли привязанный чат обсуждений
import asyncio, os, sys
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from config import SOURCES
load_dotenv('.env')
S = os.getenv('SENDER_SESSION', 'sessions/sender')
c = TelegramClient(S, int(os.getenv('API_ID', '0')), os.getenv('API_HASH', ''))
A = int(sys.argv[1]) if len(sys.argv) > 1 else 0
B = int(sys.argv[2]) if len(sys.argv) > 2 else len(SOURCES)
async def main():
    await c.connect()
    for ch in SOURCES[A:B]:
        try:
            e = await c.get_entity(ch)
            f = await c(GetFullChannelRequest(e))
            fc = f.full_chat
            print('%-24s count=%-8s hidden=%-6s linked=%s' % (
                ch, getattr(fc, 'participants_count', '?'),
                getattr(fc, 'participants_hidden', '?'),
                getattr(fc, 'linked_chat_id', '-')))
        except Exception as ex:
            print(ch, 'ERR', str(ex)[:40])
        await asyncio.sleep(3)
    await c.disconnect()
asyncio.run(main())
