import asyncio, csv, os, sys
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import (UserStatusOnline, UserStatusRecently, UserStatusLastWeek,
                               UserStatusLastMonth, UserStatusOffline)

load_dotenv()
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
S = os.getenv('SENDER_SESSION', 'sessions/sender')

CHAT = sys.argv[1] if len(sys.argv) > 1 else 'freelance_chatik0'
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 500

c = TelegramClient(S, API_ID, API_HASH)


def seg(st):
    if isinstance(st, (UserStatusOnline, UserStatusRecently)):
        return 'A', 'активный'
    if isinstance(st, UserStatusLastWeek):
        return 'B', 'на этой неделе'
    if isinstance(st, UserStatusLastMonth):
        return 'C', 'в этом месяце'
    if isinstance(st, UserStatusOffline):
        return 'D', st.was_online.strftime('%Y-%m-%d') if st.was_online else ''
    return '', ''


async def main():
    await c.connect()
    if not await c.is_user_authorized():
        print('NOT AUTHORIZED')
        return
    me = await c.get_me()
    ent = await c.get_entity(CHAT)
    seen, rows = set(), []
    st_counts = {'боты': 0, 'дубли': 0, 'удалённые': 0, 'без имени': 0}
    n = 0
    async for u in c.iter_participants(ent, limit=LIMIT):
        n += 1
        if u.bot:
            st_counts['боты'] += 1
            continue
        if getattr(u, 'deleted', False) or getattr(u, 'support', False):
            st_counts['удалённые'] += 1
            continue
        if u.id == me.id:
            continue
        un = u.username or ''
        key = un.lower() or str(u.id)
        if key in seen:
            st_counts['дубли'] += 1
            continue
        name = ' '.join(x for x in [u.first_name, u.last_name] if x).strip()
        if not name and not un:
            st_counts['без имени'] += 1
            continue
        seen.add(key)
        s, note = seg(u.status)
        rows.append([u.id, un, name, u.phone or '', s, note])
    rows.sort(key=lambda r: (r[4] or 'Z', r[2].lower()))
    fn = 'demo_%s.csv' % CHAT
    with open(fn, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['id', 'username', 'name', 'phone', 'segment', 'last_seen'])
        w.writerows(rows)
    print('просмотрено:', n, '| в базе:', len(rows))
    print('вычищено:', st_counts)
    print('с юзернеймом:', sum(1 for r in rows if r[1]))
    print('A:', sum(1 for r in rows if r[4] == 'A'), '| B:', sum(1 for r in rows if r[4] == 'B'), '| C:', sum(1 for r in rows if r[4] == 'C'))
    print('->', fn)
    await c.disconnect()


asyncio.run(main())
