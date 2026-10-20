import sys
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError

PHONE = '+380665930791'
c = TelegramClient('sessions/sender2', 24262196, '5656459bce7e76411c86173d06cc2368')
c.connect()
if c.is_user_authorized():
    me = c.get_me(); print('ME:', me.id, me.username, me.phone); sys.exit(0)

r = c.send_code_request(PHONE)
print('->', type(r.type).__name__)

while True:
    code = input('код: ').strip()
    if not code:
        continue
    if code.lower() == 'r':
        r = c.send_code_request(PHONE)
        print('->', type(r.type).__name__)
        continue
    try:
        c.sign_in(phone=PHONE, code=code, phone_code_hash=r.phone_code_hash); break
    except SessionPasswordNeededError:
        c.sign_in(password=input('2FA пароль: ').strip()); break
    except Exception as e:
        print('SIGNIN_ERR:', type(e).__name__, e)

me = c.get_me(); print('ME:', me.id, me.username, me.phone); print('ГОТОВО sessions/sender2.session')
c.disconnect()
