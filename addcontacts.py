import asyncio, os, sqlite3
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.contacts import AddContactRequest

load_dotenv()
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
S = os.getenv('SENDER_SESSION', 'sessions/sender')
c = TelegramClient(S, API_ID, API_HASH)


async def main():
    await c.connect()
    if not await c.is_user_authorized():
        print('NOT AUTHORIZED')
        return
    con = sqlite3.connect('hunter.db', timeout=30)
    rows = con.execute("select username from hits where status='new' and username is not null and is_ad=0 and is_seller=0 and is_hr=0").fetchall()
    print('к добавлению:', len(rows))
    for (u,) in rows:
        try:
            ent = await c.get_input_entity(u)
            await c(AddContactRequest(id=ent, first_name=u[:32], last_name='', phone=''))
            print('ok', u, flush=True)
        except Exception as e:
            print('fail', u, type(e).__name__, str(e)[:70], flush=True)
        await asyncio.sleep(3)
    con.close()
    await c.disconnect()


asyncio.run(main())
