import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

API = 24262196
HASH = '5656459bce7e76411c86173d06cc2368'
PNG = '/home/ubuntu/hunter/qr.png'

async def main():
    import qrcode
    c = TelegramClient('sessions/sender2', API, HASH)
    await c.connect()
    if await c.is_user_authorized():
        me = await c.get_me(); print('ME:', me.id, me.username, me.phone); return

    h = TelegramClient('/tmp/testsnd', API, HASH)
    await h.connect()

    async def push(url):
        qrcode.make(url).save(PNG)
        for tgt in ('me', '+380665930791'):
            try:
                await h.send_file(tgt, PNG, caption='QR для входа')
            except Exception as e:
                print('push err', tgt, type(e).__name__)
        print('QR отправлен')

    qr = await c.qr_login()
    print('URL:', qr.url)
    await push(qr.url)

    for i in range(60):
        try:
            await qr.wait(timeout=25)
            break
        except SessionPasswordNeededError:
            await c.sign_in(password=input('2FA: ').strip()); break
        except BaseException as e:
            n = type(e).__name__
            if 'Cancel' in n or 'Timeout' in n or 'Expired' in n:
                try:
                    await qr.recreate()
                except BaseException as e2:
                    print('recreate err', type(e2).__name__); break
                print('NEW URL:', qr.url); await push(qr.url)
            else:
                print('ERR:', n, e); break

    me = await c.get_me()
    if me:
        print('ME:', me.id, me.username, me.phone); print('ГОТОВО')
    else:
        print('не вошли')
    await c.disconnect(); await h.disconnect()

asyncio.run(main())
