import asyncio, inspect, os, re
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.auth import ResendCodeRequest

load_dotenv('/home/ubuntu/hunter/.env')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = '380665930791'

print('аргументы ResendCodeRequest:', inspect.signature(ResendCodeRequest.__init__))


def show(tag, s):
    print('%s тип: %r | следующий: %r' % (tag, s.type, s.next_type))


def mkresend(phone, h):
    try:
        return ResendCodeRequest(phone=phone, phone_code_hash=h)
    except TypeError:
        return ResendCodeRequest(phone_number=phone, phone_code_hash=h)


async def main():
    c = TelegramClient('sessions/login2', API_ID, API_HASH)
    await c.connect()
    s = await c.send_code_request(PHONE)
    show('>>> запрос 1.', s)
    for i in range(8):
        v = input('код, либо r = запросить заново: ').strip()
        if v.lower() == 'r':
            try:
                s = await c(mkresend(PHONE, s.phone_code_hash))
                show('>>> повтор.', s)
            except Exception as e:
                print('повтор не прошёл:', type(e).__name__, str(e)[:100])
            continue
        code = re.sub(r'\D', '', v)
        try:
            await c.sign_in(phone=PHONE, code=code, phone_code_hash=s.phone_code_hash)
            print('OK', await c.get_me())
            break
        except SessionPasswordNeededError:
            await c.sign_in(password=input('пароль 2FA: ').strip())
            print('OK', await c.get_me())
            break
        except Exception as e:
            print('не принят:', type(e).__name__)
    await c.disconnect()


asyncio.run(main())
