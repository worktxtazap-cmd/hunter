# demand2.py - аудит направлений: спрос, предложение, цены, срочность
import asyncio, json, os, re
from collections import Counter
from dotenv import load_dotenv
from telethon import TelegramClient
from config import SOURCES
load_dotenv('.env')
S = os.getenv('SENDER_SESSION', 'sessions/sender')
c = TelegramClient(S, int(os.getenv('API_ID', '0')), os.getenv('API_HASH', ''))
DIRS = {
 'чистка баз': ['чистк', 'валидац', 'проверк баз', 'почистить баз'],
 'базы': ['база', 'базы', 'базу', 'выгрузк', 'контакты'],
 'рассылка': ['рассылк', 'инвайт', 'прогрев'],
 'парсинг': ['парсинг', 'парсер', 'спарсить', 'скрап'],
 'боты': ['бот ', 'бота', 'телеграм-бот'],
 'бот-магазин': ['бот-магазин', 'автоворонк'],
 'касса/оплата': ['приём платеж', 'касс', 'cryptobot'],
 'аккаунты': ['аккаунт', 'акки', 'отлежк'],
 'прокси': ['прокси', 'socks', 'mtproto'],
 'инвайт подписчиков': ['подписчик', 'накрутк'],
 'архив каналов': ['выгрузк канал', 'архив канал'],
 'сайт/лендинг': ['лендинг', 'верстк'],
 'дизайн': ['дизайн', 'логотип', 'баннер'],
 'смм/таргет': ['смм', 'таргет'],
 'видео/рилс': ['монтаж', 'рилс', 'reels'],
}
DEM = ['ищу', 'ищем', 'нужен', 'нужна', 'нужно', 'требуется', 'куплю', 'интересует']
OFF = ['предлагаю', 'оказываю', 'выполню', 'возьму', 'услуги', 'прайс', 'сделаю']
URG = ['срочно', 'сегодня', 'быстро', 'горит']
PRICE = re.compile('([0-9][0-9 ]{0,7}) ?(грн|руб|usd|usdt|ton|\\$)', re.I)
def chats():
    s = set(SOURCES)
    for f in os.listdir('out'):
        if f.endswith('_targets.json'):
            try: s.update(json.load(open('out/' + f)))
            except Exception: pass
    return sorted(s)
async def main():
    await c.connect()
    ch = chats()
    print('чатов:', len(ch))
    dem, off, urg, pr = Counter(), Counter(), Counter(), {}
    n = 0
    for name in ch:
        try: ent = await c.get_entity(name)
        except Exception: continue
        try:
            async for m in c.iter_messages(ent, limit=1500):
                t = (m.message or '').lower()
                if not t: continue
                n += 1
                d = any(w in t for w in DEM)
                o = any(w in t for w in OFF)
                u = any(w in t for w in URG)
                for k, ws in DIRS.items():
                    if any(w in t for w in ws):
                        if d: dem[k] += 1
                        if o: off[k] += 1
                        if u: urg[k] += 1
                        for mm in PRICE.finditer(t):
                            v = int(re.sub(' ', '', mm.group(1)))
                            cu = mm.group(2).lower()
                            if 'грн' in cu: v = v / 42
                            elif 'руб' in cu: v = v / 90
                            if 1 <= v <= 2000: pr.setdefault(k, []).append(v)
        except Exception as ex:
            print('skip', name, str(ex)[:25])
        print('ok', name)
    print('=== сообщений', n)
    print('%-20s %7s %7s %6s %6s %7s' % ('направление','просят','предлаг','отн','срочн','цена'))
    rows = []
    for k in DIRS:
        d, o = dem[k], off[k]
        ps = sorted(pr.get(k, []))
        med = ps[len(ps)//2] if ps else 0
        rows.append(((d / o) if o else float(d), k, d, o, urg[k], med))
    for r, k, d, o, u, med in sorted(rows, reverse=True):
        print('%-20s %7d %7d %6.1f %6d %7.1f' % (k, d, o, r, u, med))
    json.dump({'dem': dem, 'off': off, 'urg': urg, 'msgs': n}, open('out/demand2.json', 'w'), ensure_ascii=False)
    await c.disconnect()
asyncio.run(main())
