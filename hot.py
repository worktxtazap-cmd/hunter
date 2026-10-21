# hot.py - горячие запросы: готовый ответ в Избранное со ссылкой на сообщение
import asyncio, os, sqlite3
from dotenv import load_dotenv
from telethon import TelegramClient
import templates
load_dotenv('.env')
DB = os.getenv('HUNTER_DB', 'hunter.db')
SESSION = os.getenv('HOT_SESSION', 'sessions/hot.session')
MIN = int(os.getenv('HOT_MIN_SCORE', '7'))
LIM = int(os.getenv('HOT_LIMIT', '15'))
async def main():
    con = sqlite3.connect(DB, timeout=30)
    rows = con.execute(
        "select id, chat, msg_id, username, keyword, text from hits "
        "where status='new' and username is not null and score>=? "
        "and is_ad=0 and is_seller=0 and is_hr=0 and is_closed=0 "
        "order by id desc limit ?", (MIN, LIM)).fetchall()
    pend = con.execute("select count(*) from hits where status='hot'").fetchone()[0]
    if pend >= int(os.getenv('HOT_MAX_PEND', '25')):
        print('в Избранном уже %d неотвеченных, хватит' % pend); return
    if not rows:
        print('горячих нет'); return
    c = TelegramClient(SESSION, int(os.getenv('API_ID','0')), os.getenv('API_HASH',''))
    await c.connect()
    if not await c.is_user_authorized():
        print('NOT AUTHORIZED', SESSION); return
    await c.send_message('me', 'ОТВЕТЫ В ЧАТЫ, %d шт. тапни ссылку и ответь в чате' % len(rows))
    for hid, chat, mid, u, kw, txt in rows:
        snip = ' '.join((txt or '').split())[:110]
        body = 'https://t.me/%s/%s\n@%s\nчто искал: %s\n\n%s\n\n%s' % (chat, mid, u, snip, templates.pick(kw, txt, chat), templates.LINK)
        await c.send_message('me', body)
        con.execute("update hits set status='hot' where id=?", (hid,))
        print('@' + u, chat)
    con.commit()
    await c.disconnect()
    print('готово:', len(rows))
asyncio.run(main())
