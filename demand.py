# demand.py - аудит спроса и предложения по категориям
import asyncio, json, os
from collections import Counter
from dotenv import load_dotenv
from telethon import TelegramClient
from config import SOURCES
load_dotenv('.env')
S = os.getenv('SENDER_SESSION', 'sessions/sender')
c = TelegramClient(S, int(os.getenv('API_ID', '0')), os.getenv('API_HASH', ''))
CATS = {
 'базы': ['база', 'базы', 'базу', 'контакты', 'выгрузк'],
 'парсинг': ['парсинг', 'парсер', 'спарсить', 'скрап'],
 'рассылка': ['рассылк', 'инвайт', 'прогрев'],
 'боты': ['бот', 'бота', 'боте'],
 'аккаунты': ['аккаунт', 'акки', 'отлежк'],
 'чистка': ['чистк', 'проверк', 'валид', 'дубл'],
}
DEM = ['ищу', 'ищем', 'нужен', 'нужна', 'нужно', 'требуется', 'куплю', 'интересует', 'кто может']
OFF = ['предлагаю', 'оказываю', 'выполню', 'возьму', 'услуги', 'прайс', 'сделаю']
def chats():
    s = set(SOURCES)
    for f in os.listdir('out'):
        if f.endswith('_targets.json'):
            try:
                s.update(json.load(open('out/' + f)))
            except Exception:
                pass
    return sorted(s)
async def main():
    await c.connect()
    ch = chats()
    print('чатов:', len(ch))
    dem, off, n = Counter(), Counter(), 0
    for name in ch:
        try:
            ent = await c.get_entity(name)
        except Exception:
            continue
        k = 0
        try:
            async for m in c.iter_messages(ent, limit=1500):
                t = (m.message or '').lower()
                if not t:
                    continue
                k += 1
                for cat, ws in CATS.items():
                    if any(w in t for w in ws):
                        if any(w in t for w in DEM):
                            dem[cat] += 1
                        if any(w in t for w in OFF):
                            off[cat] += 1
        except Exception as ex:
            print('skip', name, str(ex)[:30])
        n += k
        print('ok', name, k)
    print('=== сообщений', n)
    print('%-10s %7s %7s %6s' % ('категория', 'просят', 'предлаг', 'отн'))
    for cat in CATS:
        d, o = dem[cat], off[cat]
        print('%-10s %7d %7d %6.1f' % (cat, d, o, (d / o) if o else float(d)))
    json.dump({'dem': dem, 'off': off, 'msgs': n}, open('out/demand.json', 'w'), ensure_ascii=False)
    await c.disconnect()
asyncio.run(main())