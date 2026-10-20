import asyncio, os
from dotenv import load_dotenv
from telethon import TelegramClient

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
    await c.send_message('SpamBot', '/start')
    await asyncio.sleep(6)
    async for m in c.iter_messages('SpamBot', limit=3):
        print('---', m.date, '---')
        print((m.message or '')[:900])
    await c.disconnect()


asyncio.run(main())
