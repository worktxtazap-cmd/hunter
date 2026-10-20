import sys
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError

c = TelegramClient('sessions/sender2', 24262196, '5656459bce7e76411c86173d06cc2368')
c.connect()
if c.is_user_authorized():
    me = c.get_me(); print('ME:', me.id, me.username, me.phone); sys.exit(0)

qr = c.qr_login()
print('=== ССЫЛКА ===')
print(qr.url)
print('==============')

for i in range(30):
    try:
        qr.wait(timeout=20)
        break
    except SessionPasswordNeededError:
        c.sign_in(password=input('2FA пароль: ').strip()); break
    except Exception as e:
        n = type(e).__name__
        if 'Timeout' in n:
            qr.recreate()
            print('=== НОВАЯ ССЫЛКА ===')
            print(qr.url)
        else:
            print('ERR:', n, e); break

me = c.get_me(); print('ME:', me.id, me.username, me.phone); print('ГОТОВО')
