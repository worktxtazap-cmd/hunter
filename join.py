# join.py - вступить в источники, чтобы читать состав
import asyncio, os, sys
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.errors import UserAlreadyParticipantError
from config import SOURCES
load_dotenv('.env')
S = os.getenv('SENDER_SESSION', 'sessions/sender')
c = TelegramClient(S, int(os.getenv('API_ID', '0')), os.getenv('API_HASH', ''))
A = int(sys.argv[1]) if len(sys.argv) > 1 else 0
B = int(sys.argv[2]) if len(sys.argv) > 2 else len(SOURCES)
async def main():
    await c.connect()
    print('сессия:', S)
    for ch in SOURCES[A:B]:
        try:
            e = await c.get_entity(ch)
            await c(JoinChannelRequest(e))
            print('joined', ch)
        except UserAlreadyParticipantError:
            print('already', ch)
        except Exception as ex:
            print('fail', ch, str(ex)[:50])
        await asyncio.sleep(95)
    await c.disconnect()
asyncio.run(main())
