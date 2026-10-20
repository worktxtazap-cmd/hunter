# join2.py - вступление в цели из файла, с отработкой FloodWait
import asyncio, json, os, sys
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.errors import UserAlreadyParticipantError, FloodWaitError
load_dotenv('.env')
S = os.getenv('SENDER_SESSION', 'sessions/sender')
c = TelegramClient(S, int(os.getenv('API_ID', '0')), os.getenv('API_HASH', ''))
TG = json.load(open(sys.argv[1]))
A = int(sys.argv[2]) if len(sys.argv) > 2 else 0
B = int(sys.argv[3]) if len(sys.argv) > 3 else len(TG)
async def main():
    await c.connect()
    print('целей:', len(TG))
    for t in TG[A:B]:
        try:
            e = await c.get_entity(t)
        except Exception as ex:
            print('entity fail', t, str(ex)[:35]); continue
        for attempt in (1, 2):
            try:
                await c(JoinChannelRequest(e))
                print('joined', t); break
            except UserAlreadyParticipantError:
                print('already', t); break
            except FloodWaitError as ex:
                print('wait', ex.seconds, t)
                await asyncio.sleep(ex.seconds + 5)
            except Exception as ex:
                print('fail', t, str(ex)[:40]); break
        await asyncio.sleep(25)
    await c.disconnect()
asyncio.run(main())
