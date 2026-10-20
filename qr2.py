import sys
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError

API = 24262196
HASH = '5656459bce7e76411c86173d06cc2368'

c = TelegramClient('sessions/sender2', API, HASH)
c.connect()
if c.is_user_authorized():
    me = c.get_me(); print('ME:', me.id, me.username, me.phone); sys.exit(0)

h = TelegramClient('/tmp/testsnd', API, HASH)
h.connect()
print('helper auth:', h.is_user_authorized())

def push(url):
    try:
        h.send_message('+380665930791', '[НАЖМИ СЮДА](%s)' % url)
        print('ссылка отправлена в чат')
    except Exception as e:
        print('push err:', type(e).__name__, e)

qr = c.qr_login()
print('URL:', qr.url)
push(qr.url)

for i in range(40):
    try:
        qr.wait(timeout=20)
        break
    except SessionPasswordNeededError:
        c.sign_in(password=input('2FA: ').strip()); break
    except Exception as e:
        n = type(e).__name__
        if 'Timeout' in n:
            qr.recreate(); print('NEW URL:', qr.url); push(qr.url)
        else:
            print('ERR:', n, e); break

me = c.get_me(); print('ME:', me.id, me.username, me.phone); print('ГОТОВО')
