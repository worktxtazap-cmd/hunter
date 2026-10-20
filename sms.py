import sys, time, inspect
from telethon.sync import TelegramClient
from telethon import functions, types
from telethon.errors import SessionPasswordNeededError

API_ID = 24262196
API_HASH = '5656459bce7e76411c86173d06cc2368'
PHONE = '+380665930791'
SESSION = '/home/ubuntu/hunter/sessions/sender2'

P = list(inspect.signature(types.CodeSettings.__init__).parameters)
print('CodeSettings:', P)
SET = types.CodeSettings(**{n: True for n in P if n in ('allow_flashcall','current_number','allow_app_hash','allow_missed_call','force_sms')})

c = TelegramClient(SESSION, API_ID, API_HASH)
c.connect()
if c.is_user_authorized():
    me = c.get_me(); print('ME:', me.id, me.username, me.phone); sys.exit(0)

def t(s): return type(s.type).__name__

sent = None
for i in range(1, 9):
    time.sleep(3)
    try:
        if sent is None:
            sent = c(functions.auth.SendCodeRequest(phone_number=PHONE, api_id=API_ID, api_hash=API_HASH, settings=SET))
        else:
            sent = c(functions.auth.ResendCodeRequest(phone_number=PHONE, phone_code_hash=sent.phone_code_hash))
        print(i, '->', t(sent), '| next:', type(sent.next_type).__name__ if sent.next_type else None, '| timeout:', sent.timeout)
    except Exception as e:
        print(i, 'ERR:', type(e).__name__); sent = None; continue
    if t(sent) != 'SentCodeTypeApp':
        print('>>> доставка НЕ в приложение:', t(sent)); break

if sent is None:
    print('код не запросился'); c.disconnect(); sys.exit(1)

while True:
    code = input('код, либо r = ещё раз: ').strip()
    if code.lower() == 'r':
        try:
            sent = c(functions.auth.ResendCodeRequest(phone_number=PHONE, phone_code_hash=sent.phone_code_hash))
            print('->', t(sent))
        except Exception as e:
            print('ERR:', type(e).__name__)
        continue
    if not code: continue
    try:
        c.sign_in(phone=PHONE, code=code, phone_code_hash=sent.phone_code_hash); break
    except SessionPasswordNeededError:
        c.sign_in(password=input('2FA пароль: ').strip()); break
    except Exception as e:
        print('SIGNIN_ERR:', type(e).__name__, e)

me = c.get_me(); print('ME:', me.id, me.username, me.phone); print('ГОТОВО sessions/sender2.session')
c.disconnect()
