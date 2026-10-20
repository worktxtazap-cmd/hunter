# targets2.py - только реальные группы (megagroup), где состав читается
import asyncio, json, os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from config import SOURCES
load_dotenv('.env')
S = os.getenv('SENDER_SESSION', 'sessions/sender')
c = TelegramClient(S, int(os.getenv('API_ID', '0')), os.getenv('API_HASH', ''))
async def fc_of(e):
    return (await c(GetFullChannelRequest(e))).full_chat
async def main():
    await c.connect()
    good, bad = [], []
    for ch in SOURCES:
        try:
            e = await c.get_entity(ch)
            fc = await fc_of(e)
        except Exception as ex:
            bad.append([ch, 'err ' + str(ex)[:30]]); continue
        if getattr(e, 'megagroup', False):
            if not getattr(fc, 'participants_hidden', True):
                good.append([ch, 'group', getattr(fc, 'participants_count', '?')])
            else:
                bad.append([ch, 'group, hidden'])
            continue
        lid = getattr(fc, 'linked_chat_id', None)
        if not lid:
            bad.append([ch, 'channel, no linked']); continue
        try:
            le = await c.get_entity(lid)
            lf = await fc_of(le)
        except Exception as ex:
            bad.append([ch, 'linked err']); continue
        if getattr(le, 'megagroup', False) and not getattr(lf, 'participants_hidden', True):
            good.append([getattr(le, 'username', str(lid)), 'linked-group',
                         getattr(lf, 'participants_count', '?')])
        else:
            bad.append([ch, 'linked not group'])
        await asyncio.sleep(3)
    os.makedirs('out', exist_ok=True)
    json.dump([g[0] for g in good], open('out/targets2.json', 'w'), ensure_ascii=False)
    print('ГОДНЫХ', len(good))
    for g in good: print('  OK', g)
    print('МИМО', len(bad))
    for b in bad: print('  --', b)
    await c.disconnect()
asyncio.run(main())
