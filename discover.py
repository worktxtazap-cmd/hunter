# discover.py - поиск источников по нише: группы, состав читается, от 3000 человек
import asyncio, json, os, sys
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from niches import KEYWORDS, MIN_MEMBERS, MAX_CHATS
load_dotenv('.env')
S = os.getenv('SENDER_SESSION', 'sessions/sender')
c = TelegramClient(S, int(os.getenv('API_ID', '0')), os.getenv('API_HASH', ''))
NICHE = sys.argv[1]
async def main():
    await c.connect()
    seen, cand = set(), []
    for q in KEYWORDS.get(NICHE, []):
        try:
            res = await c(SearchRequest(q=q, limit=50))
        except Exception as ex:
            print('fail', q, str(ex)[:40]); continue
        for ch in res.chats:
            u = getattr(ch, 'username', None)
            if not u or u in seen: continue
            seen.add(u)
            if not getattr(ch, 'megagroup', False): continue
            n = getattr(ch, 'participants_count', 0) or 0
            if n < MIN_MEMBERS: continue
            cand.append((u, n))
        await asyncio.sleep(2)
    cand.sort(key=lambda x: -x[1])
    good = []
    for u, n in cand[:80]:
        try:
            e = await c.get_entity(u)
            fc = (await c(GetChannelFullRequest(e))).full_chat if False else (await c(GetFullChannelRequest(e))).full_chat
            if getattr(fc, 'participants_hidden', True):
                print('hidden', u, n); continue
            good.append([u, n]); print('OK', u, n)
        except Exception as ex:
            print('err', u, str(ex)[:35])
        await asyncio.sleep(2)
        if len(good) >= MAX_CHATS: break
    os.makedirs('out', exist_ok=True)
    json.dump([g[0] for g in good], open('out/%s_targets.json' % NICHE, 'w'), ensure_ascii=False)
    print('ИТОГО', len(good), '-> out/%s_targets.json' % NICHE)
    await c.disconnect()
asyncio.run(main())
