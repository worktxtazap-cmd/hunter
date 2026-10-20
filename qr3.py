import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

API = 24262196
HASH = '5656459bce7e76411c86173d06cc2368'

async def main():
    c = TelegramClient('sessions/sender2', API, HASH)
    await c.connect()
    if await c.is_user_authorized():
        me = await c.get_me(); print('ME:', me.id, me.username, me.phone); return

    h = TelegramClient('/tmp/testsnd', API, HASH)
    await h.connect()
    print('helper auth:', await h.is_user_authorized())

    async def push(url):
        try:
            await h.send_message('+380665930791', '[НАЖМИ СЮДА](%s)' % url)
            print('ссылка отправлена в чат')
        except Exception as e:
            print('push err:', type(e).__name__, e)

    qr = await c.qr_login()
    print('URL:', qr.url)
    await push(qr.url)

    for i in range(40):
        try:
            await qr.wait(timeout=20)
            break
        except SessionPasswordNeededError:
            await c.sign_in(password=input('2FA: ').strip()); break
        except Exception as e:
            n = type(e).__name__
            if 'Timeout' in n or 'Expired' in n:
                await qr.recreate(); print('NEW URL:', qr.url); await push(qr.url)
            else:
                print('ERR:', n, e); break

    me = await c.get_me()
    if me:
        print('ME:', me.id, me.username, me.phone); print('ГОТОВО')
    else:
        print('не вошли')
    await c.disconnect(); await h.disconnect()

asyncio.run(main())
