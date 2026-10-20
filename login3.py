import sys
from telethon.sync import TelegramClient
from telethon import functions
from telethon.errors import SessionPasswordNeededError

API_ID = 24262196
API_HASH = '5656459bce7e76411c86173d06cc2368'
PHONE = '+380665930791'
SESSION = '/home/ubuntu/hunter/sessions/sender2'

c = TelegramClient(SESSION, API_ID, API_HASH)
c.connect()
print('AUTH:', c.is_user_authorized())
if c.is_user_authorized():
    me = c.get_me(); print('ME:', me.id, me.username, me.phone); c.disconnect(); sys.exit(0)

def show(s):
    print('TYPE:', type(s.type).__name__, '| NEXT:', type(s.next_type).__name__ if s.next_type else None, '| TIMEOUT:', s.timeout)

sent = None
for kw in ({'force_sms': True}, {'force_sms': False}, {}):
    try:
        sent = c.send_code_request(PHONE, **kw)
        print('kw =', kw); show(sent); break
    except Exception as e:
        print('SEND_ERR:', type(e).__name__, e); sent = None

if sent is None:
    print('не вышло запросить код'); c.disconnect(); sys.exit(1)

while True:
    code = input('код, либо r = запросить заново: ').strip()
    if code.lower() == 'r':
        try:
            sent = c(functions.auth.ResendCodeRequest(phone_number=PHONE, phone_code_hash=sent.phone_code_hash))
            show(sent)
        except Exception as e:
            print('RESEND_ERR:', type(e).__name__, e)
        continue
    if not code: continue
    try:
        c.sign_in(phone=PHONE, code=code, phone_code_hash=sent.phone_code_hash)
        break
    except SessionPasswordNeededError:
        pw = input('пароль 2FA: ').strip()
        c.sign_in(password=pw); break
    except Exception as e:
        print('SIGNIN_ERR:', type(e).__name__, e)

me = c.get_me()
print('ME:', me.id, me.username, me.phone)
print('ГОТОВО: sessions/sender2.session')
c.disconnect()
