import asyncio, os, re
from dotenv import load_dotenv
from telethon import TelegramClient
import config
load_dotenv('.env')
API_ID = int(os.getenv('API_ID','0')); API_HASH = os.getenv('API_HASH','')
PROD = [r'\bбаз', r'\bпарс', r'\bбот', r'\bрассылк', r'\bинвайт', r'\bвыгрузк', r'\bскрап', r'\bконтакт']
DEM  = [r'\bнужн', r'\bищу', r'\bищем', r'\bкупл', r'\bхочу', r'\bпродаст', r'\bпосоветуй',
        r'\bподскаж', r'\bзакаж', r'\bнадо', r'\bтребу', r'\bпокупа', r'\bскуп', r'\bприобрест', r'\bгде\b']
RP = [re.compile(x) for x in PROD]; RD = [re.compile(x) for x in DEM]
known = set(x.lower().lstrip('@') for x in config.SOURCES)

def hit(low):
    pp = [m.start() for r in RP for m in r.finditer(low)]
    dd = [m.start() for r in RD for m in r.finditer(low)]
    if not pp or not dd: return False
    return min(abs(a-b) for a in pp for b in dd) <= 25

async def main():
    c = TelegramClient('sessions/drafts1.session', API_ID, API_HASH)
    await c.connect()
    print('podklyuchen:', (await c.get_me()).username)
    res, seen = [], 0
    async for d in c.iter_dialogs():
        ent = d.entity
        if not (d.is_group and getattr(ent, 'megagroup', False)):
            continue
        un = (getattr(ent, 'username', None) or '').lower()
        if not un:
            continue
        seen += 1
        if seen > 120: break
        try:
            msgs = await c.get_messages(ent, limit=40)
        except Exception:
            continue
        cnt, samp = 0, []
        for m in msgs:
            if not m.message: continue
            low = ' '.join(m.message.lower().split())
            if hit(low):
                cnt += 1
                if len(samp) < 2: samp.append(low[:65])
        if cnt >= 2:
            res.append((cnt, un, d.title or '', 'ZNak' if un in known else 'NOVY', samp))
        await asyncio.sleep(0.3)
    res.sort(reverse=True)
    print('proskanirovano grupp:', seen, '| plotnost >=2:', len(res))
    for cnt, un, title, tag, samp in res[:40]:
        print(cnt, tag, '@'+un, '|', title[:40])
        for s in samp: print('     ', s)
    await c.disconnect()
asyncio.run(main())
