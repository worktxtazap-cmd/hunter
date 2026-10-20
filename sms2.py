import sys, time
from telethon.sync import TelegramClient
from telethon import functions
from telethon.errors import SessionPasswordNeededError, FloodWaitError

API_ID = 24262196
API_HASH = '5656459bce7e76411c86173d06cc2368'
PHONE = '+380665930791'
SESSION = '/home/ubuntu/hunter/sessions/sender2'

def t(s): return type(s.type).__name__

c = TelegramClient(SESSION, API_ID, API_HASH)
c.connect()
if c.is_user_authorized():
    me = c.get_me(); print('ME:', me.id, me.username, me.phone); sys.exit(0)

sent = None
for i in range(1, 8):
    try:
        if sent is None:
            sent = c.send_code_request(PHONE)
        else:
            sent = c(functions.auth.ResendCodeRequest(phone_number=PHONE, phone_code_hash=sent.phone_code_hash))
        print(i, '->', t(sent), '| next:', type(sent.next_type).__name__ if sent.next_type else None)
        if t(sent) != 'SentCodeTypeApp':
            print('>>> НЕ приложение, жди SMS или звонок'); break
    except FloodWaitError as e:
        print(i, 'FLOOD_WAIT', e.seconds, 'сек - жду'); time.sleep(e.seconds + 3); sent = None
    except Exception as e:
        print(i, 'ERR:', type(e).__name__, str(e)[:100]); sent = None; time.sleep(8)

if sent is None:
    print('код не запросился'); c.disconnect(); sys.exit(1)

while True:
    code = input('код, либо r = ещё раз: ').strip()
    if code.lower() == 'r':
        try:
            sent = c(functions.auth.ResendCodeRequest(phone_number=PHONE, phone_code_hash=sent.phone_code_hash)); print('->', t(sent))
        except Exception as e:
            print('ERR:', type(e).__name__, str(e)[:100])
        continue
    if not code: continue
    try:
        c.sign_in(phone=PHONE, code=code, phone_code_hash=sent.phone_code_hash); break
    except SessionPasswordNeededError:
        c.sign_in(password=input('2FA пароль: ').strip()); break
    except Exception as e:
        print('SIGNIN_ERR:', type(e).__name__, str(e)[:150])

me = c.get_me(); print('ME:', me.id, me.username, me.phone); print('ГОТОВО sessions/sender2.session')
c.disconnect()
