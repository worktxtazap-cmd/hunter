import asyncio, os, shutil
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')

SKIP = {'.venv', 'node_modules', '.git', '__pycache__', 'site-packages'}
found = []
for root, dirs, files in os.walk('/home/ubuntu'):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if f.endswith('.session'):
            p = os.path.join(root, f)
            try:
                if os.path.getsize(p) > 0:
                    found.append(p)
            except OSError:
                pass

found.sort()
print('найдено .session:', len(found))
for p in found:
    print('  ', p)


async def check(i, p):
    tmp = '/tmp/probe_%d.session' % i
    shutil.copy2(p, tmp)
    c = TelegramClient(tmp, API_ID, API_HASH)
    try:
        await c.connect()
        if await c.is_user_authorized():
            me = await c.get_me()
            print('OK   %s' % p)
            print('     id=%s @%s %s %s' % (me.id, me.username or '-', me.first_name, me.phone))
        else:
            print('--   %s не авторизована' % p)
    except Exception as e:
        print('ERR  %s %s %s' % (p, type(e).__name__, str(e)[:60]))
    finally:
        try:
            await c.disconnect()
        except Exception:
            pass


async def main():
    for i, p in enumerate(found):
        await check(i, p)


asyncio.run(main())
