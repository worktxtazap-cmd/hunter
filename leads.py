#!/usr/bin/env python3
# leads.py - GORYACHIE LIDY. Zhestkiy filtr po frazam pokupatelya.
import asyncio, os, re, sqlite3, sys
from datetime import datetime, timezone
from dotenv import load_dotenv
from telethon import TelegramClient
import templates

load_dotenv('.env')
DB = os.getenv('HUNTER_DB', 'hunter.db')
API_ID = int(os.getenv('API_ID', '0')); API_HASH = os.getenv('API_HASH', '')
SESSION = os.getenv('LEADS_SESSION', 'sessions/drafts1.session')
TARGET = os.getenv('NOTIFY_TARGET', 'me')
PER_CHAT = int(os.getenv('LEADS_PER_CHAT', '60'))
MAX_CHATS = int(os.getenv('LEADS_MAX_CHATS', '200'))
MIN = int(os.getenv('LEADS_MIN', '12'))
N = int(os.getenv('LEADS_N', '25'))

BUY = [
 (14, r'нужн\w*\s+(?:баз|выгрузк|контакт|аудитор)'),
 (14, r'ищ\w*\s+(?:баз|выгрузк|контакт)'),
 (13, r'(?:куп|скуп|покуп)\w*\s+(?:баз|контакт)'),
 (13, r'хоч\w*\s+баз'),
 (12, r'(?:собр\w*|сбор)\s+(?:баз|контакт|аудитор|участник)'),
 (12, r'нужен\s+(?:парсер|парсинг|скрапер|сборщик)'),
 (12, r'спарс\w+|пропарс\w+|парсить\s'),
 (12, r'выгруз\w*\s+(?:участник|баз|контакт)'),
 (11, r'баз[аыуеи]\s+(?:контакт|участник|данн|подписчик)'),
 (11, r'нужн\w*\s+контакт'),
 (11, r'где\s+(?:взять|найти|купить|достать)\s+(?:баз|контакт)'),
 (10, r'актуальн\w*\s+баз'),
 (10, r'есть\s+у\s+кого\s+баз'),
 (10, r'(?:посовет\w*|подскаж\w*)\s+баз'),
 (10, r'парсинг\s+(?:чат|канал|аудитор|баз)'),
 (10, r'сборщик\s+(?:баз|контакт)'),
 (14, r'нужн\w*\s+(?:бот|ботмейкер)'),
 (13, r'хоч\w*\s+бот'),
 (13, r'(?:сделать|разработать|написать|создать|заказать|запилить)\s+бот'),
 (12, r'ищ\w*\s+(?:бот|ботмейкер|разработчик)'),
 (11, r'ботмейкер|бот-?мейкер'),
 (11, r'(?:телеграм|тг|tg)\s*-?\s*бот'),
 (10, r'бот\s+(?:для|с|под|на)\b'),
 (10, r'бот\s+с\s+(?:оплат|админк|подписк|магазин)'),
 (14, r'нужн\w*\s+(?:рассылк|инвайт|инвайтер|рассыльщик|автоответчик)'),
 (12, r'(?:сделать|заказать|запустить|собрать)\s+рассылк'),
 (11, r'рассылк\w*\s+(?:по|в)\s'),
 (11, r'инвайт\w*'),
 (10, r'нужен\s+(?:инвайтер|рассыльщик)'),
 (12, r'кто\s+(?:может|сможет|сделает|умеет|поможет)\s+(?:спарс|собрать|выгруз|сделать\s+бот|написать\s+бот|запустить)'),
 (11, r'закаж\w*\s+(?:баз|бот|парс|рассылк|выгруз)'),
 (10, r'требу\w*\s+(?:баз|бот|парсер|рассылк)'),
 (10, r'интерес\w*\s+(?:баз|парсер|бот)'),
 (13, r'потрібн\w*\s+(?:баз|бот|парсер|розсилк|вигрузк)'),
 (12, r'шука\w*\s+(?:баз|бот|парсер)'),
 (11, r'потрібен\s+(?:бот|парсер)'),
 (10, r'розсилк\w*|інвайт\w*'),
]

BAD = [
 (6, r'предлага\w+'), (5, r'прода\w+\s+(?:баз|бот)'), (5, r'делаем\s+(?:бот|баз|рассылк)'),
 (4, r'оказыв\w+'), (4, r'наши\s+услуги'), (3, r'прайс'), (3, r'под\s+ключ'),
 (4, r'#вакансия'), (3, r'резюме'),
]

STOP = ('розыгрыш', 'конкурс', 'подписывайтесь', 'видел ваш пост')
PROD = [r'\bбаз', r'\bпарс', r'\bбот', r'\bрассылк', r'\bинвайт', r'\bвыгрузк', r'\bскрап', r'\bконтакт']
DEM  = [r'\bнужн', r'\bищу', r'\bищем', r'\bкупл', r'\bхочу', r'\bзакаж', r'\bнадо', r'\bтребу', r'\bпокупа', r'\bскуп', r'\bприобрест', r'\bгде\b']
RP = [re.compile(x) for x in PROD]; RD = [re.compile(x) for x in DEM]
RB = [(w, re.compile(x)) for w, x in BUY]
RK = [(w, re.compile(x)) for w, x in BAD]

def norm(t):
    t = (t or '').lower()
    t = re.sub(r'https?://\S+', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()

def near(low):
    pp = [m.start() for r in RP for m in r.finditer(low)]
    dd = [m.start() for r in RD for m in r.finditer(low)]
    if not pp or not dd: return 999
    return min(abs(a - b) for a in pp for b in dd)

def rate(text):
    low = norm(text)
    if not low or any(s in low for s in STOP): return 0, ''
    best, hits = 0, []
    for w, rx in RB:
        m = rx.search(low)
        if m:
            if w > best: best = w
            hits.append(m.group(0)[:22])
    if not hits: return 0, ''
    s = best
    if len(hits) > 1: s += 3
    if near(low) <= 25: s += 4
    s -= sum(w for w, rx in RK if rx.search(low))
    return s, '+'.join(hits[:2])

def kind(low):
    if re.search(r'бот', low): return 'бот'
    if re.search(r'рассылк|инвайт', low): return 'рассылк'
    return 'база'

def block(u, snip, low, link):
    return '%s\n@%s\nчто искал: %s\n\n%s\n\n%s' % (link, u, snip, templates.pick(kind(low), low, ''), templates.LINK)

def already(con):
    return set(r[0].lower() for r in con.execute(
        "select username from hits where username is not null and (sent_at is not null or status in ('hot','draft'))"))

async def scan(c):
    con = sqlite3.connect(DB, timeout=30)
    done = already(con)
    out, n, seen = [], 0, set()
    async for d in c.iter_dialogs():
        ent = d.entity
        if not (d.is_group and getattr(ent, 'megagroup', False)): continue
        n += 1
        if n > MAX_CHATS: break
        if n % 25 == 0: print('... чатов пройдено', n, 'найдено', len(out))
        try:
            msgs = await c.get_messages(ent, limit=PER_CHAT)
        except Exception:
            continue
        un = getattr(ent, 'username', None)
        for m in msgs:
            if m.out or not m.message: continue
            if len(m.message) < 15 or len(m.message) > 900: continue
            s, why = rate(m.message)
            if s < MIN: continue
            try: snd = await m.get_sender()
            except Exception: snd = None
            u = getattr(snd, 'username', None)
            if not u: continue
            k = u.lower()
            if k in seen: continue
            seen.add(k)
            link = ('https://t.me/%s/%s' % (un, m.id)) if un else ('https://t.me/c/%s/%s' % (ent.id, m.id))
            snip = ' '.join(m.message.split())[:110]
            out.append((s, u, link, snip, norm(m.message), k in done))
        await asyncio.sleep(0.2)
    con.close()
    out.sort(key=lambda x: -x[0])
    return out

def report(rows, limit):
    print('')
    print('=== GORYACHIE LIDY: %d ===' % len(rows))
    for s, u, link, snip, low, known in rows[:limit]:
        tag = ' [uzhe v rabote]' if known else ''
        print('')
        print(s, '@' + u + tag)
        print('  ', link)
        print('  ', snip)
        print('  otvet:', ' '.join(templates.pick(kind(low), low, '').split())[:90], '...')

async def main():
    send = '--send' in sys.argv
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.connect()
    me = await c.get_me()
    print('akkaunt:', getattr(me, 'username', None))
    rows = await scan(c)
    report(rows, N)
    if send:
        con = sqlite3.connect(DB, timeout=30)
        fresh = [r for r in rows if not r[5]][:N]
        print('')
        print('=== OTPRAVLYAYU V IZBRANNOE: %d ===' % len(fresh))
        for s, u, link, snip, low, known in fresh:
            try:
                await c.send_message(TARGET, block(u, snip, low, link))
            except Exception as e:
                print('fail', u, e); continue
            con.execute("insert or ignore into hits (chat,msg_id,username,text,keyword,score,status,found_at) values (?,?,?,?,?,?,'hot',?)",
                        (link, 0, u, snip, kind(low), s, datetime.now(timezone.utc).isoformat(timespec='seconds')))
            con.commit()
            print('ok', s, '@' + u)
            await asyncio.sleep(5)
        con.close()
    await c.disconnect()

asyncio.run(main())
