# targets.py - что реально читается: открытые каналы + их привязанные чаты
import asyncio, json, os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from config import SOURCES
load_dotenv('.env')
S = os.getenv('SENDER_SESSION', 'sessions/sender')
c = TelegramClient(S, int(os.getenv('API_ID', '0')), os.getenv('API_HASH', ''))
async def full(e):
    return (await c(GetFullChannelRequest(e))).full_chat
async def main():
    await c.connect()
    good, bad = [], []
    for ch in SOURCES:
        try:
            e = await c.get_entity(ch)
            fc = await full(e)
        except Exception as ex:
            bad.append([ch, str(ex)[:35]]); continue
        if not getattr(fc, 'participants_hidden', True):
            good.append([ch, 'open', getattr(fc, 'participants_count', '?')]); continue
        lid = getattr(fc, 'linked_chat_id', None)
        if not lid:
            bad.append([ch, 'hidden, no linked']); continue
        try:
            le = await c.get_entity(lid)
            lf = await full(le)
        except Exception as ex:
            bad.append([ch, 'linked err ' + str(ex)[:25]]); continue
        if getattr(lf, 'participants_hidden', True):
            bad.append([ch, 'linked hidden too']); continue
        good.append([getattr(le, 'username', str(lid)), 'linked',
                     getattr(lf, 'participants_count', '?')])
        await asyncio.sleep(3)
    os.makedirs('out', exist_ok=True)
    json.dump([g[0] for g in good], open('out/targets.json', 'w'), ensure_ascii=False)
    print('ГОДНЫХ', len(good))
    for g in good: print('  OK', g)
    print('МИМО', len(bad))
    for b in bad: print('  --', b)
    await c.disconnect()
asyncio.run(main())
