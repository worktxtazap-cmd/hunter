# pack.py - товар по нише: участники чатов -> чистка -> CSV + TXT
import asyncio, csv, os, sys, json
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import (UserStatusOnline, UserStatusRecently,
    UserStatusLastWeek, UserStatusLastMonth, UserStatusOffline)
from niches import NICHES
from telethon.errors import FloodWaitError
load_dotenv('.env')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
S = os.getenv('SENDER_SESSION', 'sessions/sender')
NICHE = sys.argv[1] if len(sys.argv) > 1 else 'freelance'
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
MAXCH = int(sys.argv[3]) if len(sys.argv) > 3 else 99
CHATS = json.load(open(NICHE))[:MAXCH] if NICHE.endswith('.json') else NICHES.get(NICHE, [])[:MAXCH]
TAG = NICHE.split('/')[-1].replace('.json', '')
c = TelegramClient(S, API_ID, API_HASH)
def seg(st):
    if isinstance(st, (UserStatusOnline, UserStatusRecently)): return 'A'
    if isinstance(st, UserStatusLastWeek): return 'B'
    if isinstance(st, UserStatusLastMonth): return 'C'
    if isinstance(st, UserStatusOffline): return 'D'
    return ''
def wd(st):
    return st.was_online.strftime('%Y-%m-%d') if isinstance(st, UserStatusOffline) and st.was_online else ''
DECO = '~•▪●○★☆∙'
def cname(n):
    o = []
    for ch in n:
        if o and o[-1] == ch and ch in DECO: continue
        o.append(ch)
    return ''.join(o).strip()[:32]
async def parts(ent, lim):
    try:
        async for u in c.iter_participants(ent, limit=lim):
            yield u
    except Exception as ex:
        print('  break', str(ex)[:45])

async def main():
    await c.connect()
    if not await c.is_user_authorized():
        print('NOT AUTHORIZED'); return
    me = await c.get_me()
    ppl = {}
    stats = {'боты': 0, 'удалённые': 0, 'без юзернейма': 0, 'дубли': 0, 'чатов': 0}
    for chat in CHATS:
        try:
            ent = await c.get_entity(chat)
        except Exception as e:
            print('skip', chat, e); continue
        if not getattr(ent, 'megagroup', False):
            print('skip broadcast', chat); continue
        n = 0
        async for u in parts(ent, LIMIT):
            n += 1
            if u.bot: stats['боты'] += 1; continue
            if getattr(u, 'deleted', False) or getattr(u, 'support', False):
                stats['удалённые'] += 1; continue
            if u.id == me.id: continue
            un = (u.username or '').strip()
            if not un: stats['без юзернейма'] += 1; continue
            p = ppl.get(u.id)
            if p:
                stats['дубли'] += 1; p['chats'].add(chat); continue
            nm = cname(' '.join(x for x in [u.first_name, u.last_name] if x))
            ppl[u.id] = {'username': un, 'name': nm,
                'premium': 1 if getattr(u, 'premium', False) else 0,
                'status': seg(u.status), 'last_seen': wd(u.status), 'chats': {chat}}
        stats['чатов'] += 1
        print(chat, 'просмотрено', n, '| в базе', len(ppl))
    rows = [[p['username'], uid, p['name'], '', p['premium'], p['status'],
             p['last_seen'], len(p['chats']), ';'.join(sorted(p['chats']))]
            for uid, p in ppl.items()]
    rows.sort(key=lambda r: (r[5] or 'Z', r[1]))
    os.makedirs('out', exist_ok=True)
    fn = 'out/%s_%d.csv' % (TAG, len(rows))
    with open(fn, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['username','user_id','name','phone_opt','premium',
                    'status','last_seen','seen_chats','source_chat'])
        w.writerows(rows)
    with open(fn.replace('.csv', '.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join('@' + r[0] for r in rows))
    core = sum(1 for r in rows if r[5] == 'A' and r[7] >= 2)
    print('ИТОГО', len(rows), '| премиум', sum(r[4] for r in rows), '| ядро A/2+', core)
    print('вычищено', stats)
    print('->', fn)
    await c.disconnect()
async def run():
    for i in range(6):
        try:
            await main(); return
        except FloodWaitError as e:
            print('FloodWait', e.seconds)
            await asyncio.sleep(e.seconds + 5)
asyncio.run(run())
