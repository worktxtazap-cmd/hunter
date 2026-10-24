# shop.py - vitrina nishevyh botov + kassa
import asyncio, csv, json, os, sqlite3, urllib.request
import re
from datetime import datetime, timezone, timedelta

import logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(name)s %(message)s')

from dotenv import load_dotenv
from telethon import TelegramClient, Button, events
from telethon.tl import types as tl_types
from telethon.tl import functions as tl_functions

load_dotenv('.env')
DB = os.getenv('HUNTER_DB', 'hunter.db')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
PAY_TOKEN = os.getenv('CRYPTOPAY_TOKEN', '')
OWNER = int(os.getenv('OWNER_ID', '0'))

ADMINS = set()
for _x in (os.getenv('ADMINS', '') or '').split(','):
    _x = _x.strip()
    if _x.isdigit():
        ADMINS.add(int(_x))
ADMINS.add(OWNER)
SESSION = os.getenv('SHOP_SESSION', 'sessions/shop')
USERSESSION = os.getenv('SHOP_USER_SESSION', 'sessions/shopuser.session')
DEMO_CHAT = os.getenv('DEMO_CHAT', 'onlayn_rabota')
PHOTO = 'assets/banner.png'
OUT = 'demo_out'
PAY_API = 'https://pay.crypt.bot/api/'
STARS = int(os.getenv('STARS_PER_USD', '50'))

SEED = [
 ('botparser', 'Бот-парсер', 'кидаешь ссылку на чат — бот отдаёт базу | ник, id, имя, телефон где есть | боты и дубли вычищены | файл CSV или Excel', 59, 'под ключ', 'bot'),
 ('botkassa', 'Бот-касса', 'витрина товаров прямо в боте | приём оплаты | выдача файла после оплаты | список покупателей у тебя', 59, 'под ключ', 'bot'),
 ('botzapis', 'Бот-запись', 'онлайн-запись на слоты | подтверждение клиенту | напоминание за день | все записи у тебя в одном списке', 59, 'под ключ', 'bot'),
 ('botquiz', 'Бот-квиз', 'воронка с вопросами | собирает контакт человека | отдаёт лид-магнит | уведомляет тебя о каждом', 59, 'под ключ', 'bot'),
 ('botreply', 'Бот-автоответчик', 'отвечает первым на входящие | держит скрипт | зовёт тебя в диалог | работает 24/7', 49, 'под ключ', 'bot'),
 ('base1', 'База: 1 чат', 'ник · id · имя · телефон где есть | боты и дубли вычищены | сегмент A/B/C/D', 5, 'за чат', 'base'),
 ('base3', 'База: 3 чата', 'то же самое, три чата | выгоднее по цене', 12, 'за 3 чата', 'base'),
 ('base10', 'База: 10 чатов', 'то же самое, десять чатов | максимальный охват', 30, 'за 10 чатов', 'base'),
 ('clean', 'Чистка базы', 'уберу ботов и дубли из твоей базы | размечу активность | верну Excel', 10, 'за базу', 'base'),
 ('rassylka', 'Рассылка 1000', 'отправлю твоё сообщение по 1000 живым | отчёт по доставке', 30, 'за 1000', 'base'),
 ('podpiska', 'Подписка на базы', 'свежие срезы каждые 2 дня | доступ к новым чатам | приоритет в очереди', 19, 'в месяц', 'sub'),
]

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def db():
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    return con

def seed():
    con = db()
    for code, title, descr, price, unit, delivery in SEED:
        try:
            con.execute("insert or replace into products (code,title,descr,price,unit,delivery,active) values (?,?,?,?,?,?,1)",
                        (code, title, descr, price, unit, delivery))
        except Exception as ex:
            print('seed', code, type(ex).__name__, ex)
    try:
        con.execute("insert or replace into products (code,title,descr,price,unit,delivery,active) values ('serv','Обслуживание бота','хостинг, правки и обновления в течение месяца','9','мес','sub',1)")
    except Exception as ex:
        print('seed serv', type(ex).__name__, ex)
    try:
        con.execute("update products set active=0 where code in ('bot','rassylka','podpiska')")
    except Exception:
        pass
    if not con.execute("select code from coupons where code='START'").fetchone():
        until = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(timespec='seconds')
        con.execute("insert into coupons (code, percent, amount_off, max_uses, used, active, until, promo) values ('START',10,0,50,0,1,?,1)", (until,))
        print('START kupon sozdan do', until[:16])
    con.commit()
    con.close()


def pay(method, **params):
    req = urllib.request.Request(
        PAY_API + method,
        data=json.dumps(params).encode(),
        headers={'Crypto-Pay-API-Token': PAY_TOKEN, 'Content-Type': 'application/json',
                 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120'})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    if not d.get('ok'):
        raise RuntimeError(str(d))
    return d['result']

def bot_api(method, **params):
    req = urllib.request.Request('https://api.telegram.org/bot%s/%s' % (BOT_TOKEN, method),
                                 data=json.dumps(params).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    if not d.get('ok'):
        raise RuntimeError(str(d))
    return d.get('result')


def product(code):
    con = db()
    r = con.execute("select * from products where code=?", (code,)).fetchone()
    con.close()
    return r

def disc_text(c):
    try:
        if c['percent']:
            return 'минус %d%%' % c['percent']
        return 'минус %g' % float(c['amount_off'])
    except Exception:
        return 'скидка'


def coupon(code):
    if not code:
        return None
    con = db()
    r = con.execute("select * from coupons where upper(code)=? and active=1", (code.upper(),)).fetchone()
    con.close()
    if not r:
        return None
    if r['max_uses'] and r['used'] >= r['max_uses']:
        return None
    try:
        if r['until'] and r['until'] < now_iso():
            return None
    except Exception:
        pass
    return r


def price_with(c, cop):
    p = float(c['price'])
    if not cop:
        return round(p, 2), 0.0
    if cop['percent']:
        off = round(p * cop['percent'] / 100.0, 2)
    else:
        off = float(cop['amount_off'])
    return round(max(0.5, p - off), 2), off

def box(title, body):
    if body:
        return '<b>' + title.upper() + '</b>\n\n' + '\n'.join(body)
    return '<b>' + title.upper() + '</b>'

def card(c, cop=None):
    price, off = price_with(c, cop)
    body = (c['descr'].split(' | ') if c['descr'] else [])
    txt = box(c['title'], body)
    if off:
        txt += '\n<s>%g</s> %s по купону %s' % (float(c['price']), disc_text(cop), cop['code'])
    if cop:
        try:
            if cop['until']:
                txt += '\nкупон действует до %s' % cop['until'][:16].replace('T', ' ')
        except Exception:
            pass
    txt += '\n<b>%g</b> %s' % (price, c['unit'])
    return txt


STATE = {}

def menu_kb():
    con = db()
    pr = dict(con.execute('select code, price from products where active=1').fetchall())
    con.close()
    def b(code, name):
        p = pr.get(code)
        t = ('%g' % p) if p is not None else ''
        return Button.inline((name + ' — ' + t).strip(' —'), ('p:' + code).encode())
    def sep(t):
        return Button.inline(t, b'noop')
    rows = [
        [sep('— БОТЫ —')],
        [b('botparser', 'Парсер базы из чата')],
        [b('botkassa', 'Бот-касса')],
        [b('botzapis', 'Бот-запись')],
        [b('botquiz', 'Бот-квиз')],
        [b('botreply', 'Автоответчик')],
        [sep('— БАЗЫ —')],
        [b('base1', '1 чат'), b('base3', '3 чата')],
        [b('base10', '10 чатов'), b('clean', 'чистка')],
        [Button.inline('о боте', b'about'), Button.inline('оставить контакт', b'contact')],
    [Button.inline('реферальный код', b'ref'), Button.inline('подобрать базу', b'fqmenu')],
        [Button.inline('купон', b'coupon'), Button.inline('акции', b'promo')],
        [Button.inline('кошелёк', b'wallet')],
    ]
    return rows


def back_kb():
    return [[Button.inline('назад в меню', b'menu')]]

INFO = {
    'botparser': ('своя база из чужих чатов — для рассылки, приглашений и продаж',
                  'CSV с никами, именами и телефонами — открывается в Excel',
                  '@onlayn_rabota: 1000 живых ников за пару минут'),
    'botkassa': ('продажи без тебя: клиент выбрал, оплатил, получил товар',
                 'каталог в кнопках, приём оплаты, автовыдача файла или доступа',
                 'клиент жмёт товар, платит и сразу получает файл'),
    'botzapis': ('клиенты сами выбирают время, ты не переписываешься',
                 'слоты, подтверждение клиенту, напоминание за день, один список записей',
                 'клиент выбрал время и получил подтверждение с напоминанием'),
    'botquiz': ('собирает заявки вопросами, а не сухим «здравствуйте»',
                'воронка из двух вопросов, контакт и лид-магнит в конце',
                'бюджет, опыт, @ник — бот отдаёт лид-магнит и сохраняет контакт'),
    'botreply': ('отвечает первым и держит клиента, пока ты занят',
                 'скрипт ответов и передача диалога тебе в нужный момент',
                 'вопрос про цену: бот отвечает сам и зовёт тебя в диалог'),
}

EXAMPLES = {
    'botparser': 'чат @onlayn_rabota\n100 живых ников за минуту\n\nid;username;first_name\n77123456;@ivan_p;Иван\n77123457;@marina_k;Марина\n77123458;@petr99;Пётр',
    'botkassa': 'клиент открыл каталог и выбрал товар\nклиент оплатил 59\nбот отдал файл и чек, заказ упал в базу',
    'botzapis': 'клиент выбрал «сегодня 15:00»\nбот подтвердил и напомнит за день\nтвои записи: сегодня 15:00, завтра 12:00',
    'botquiz': 'вопрос 1: бюджет до 50к\nвопрос 2: рассылку не пробовал\n@ник сохранён, лид-магнит отправлен',
    'botreply': 'клиент: сколько стоит?\nбот: от 5000, зависит от объёма\nбот зовёт тебя в диалог',
}


def bot_info(c, price):
    a, b, _ = INFO.get(c['code'], ('', '', ''))
    ex = EXAMPLES.get(c['code'], '')
    extra = ''
    if c['code'] == 'botparser':
        extra = '\n\nв демо до %d ников, на заказе до %d' % (DEMO_LIMIT, PARSE_LIMIT)
    return ('<b>%s</b>\n\n<b>зачем:</b> %s\n<b>на выходе:</b> %s\n\n<b>пример:</b>\n<code>%s</code>%s\n\n'
            'демо ниже живое, тыкай бесплатно.\nцена: <b>%g</b>') % (c['title'], a, b, ex, extra, price)


def bot_info_kb(code, price):
    return [[Button.inline('запустить демо', ('dm:' + code + ':go').encode())],
            [Button.inline('заказать · %g' % price, b'buy')],
            [Button.inline('назад в меню', b'menu')]]


BOT_USERNAME = os.getenv('BOT_USERNAME', 'hunter_pay_bot')


def ref_link(uid):
    return 'https://t.me/%s?start=ref%s' % (BOT_USERNAME, uid)


def ref_text(uid):
    con = db()
    con.execute("insert or ignore into botleads (uid, first_seen, last_seen) values (?,?,?)", (uid, now_iso(), now_iso()))
    bought = con.execute("select count(*) from orders where client_id=? and status <> 'new' and coalesce(note,'') <> 'demo'", (uid,)).fetchone()[0]
    inv = con.execute("select count(*) from botleads where ref_by=?", (uid,)).fetchone()[0]
    paid = con.execute("select count(*) from botleads where ref_by=? and ref_paid=1", (uid,)).fetchone()[0]
    my = con.execute("select code, used, max_uses from coupons where code=? and active=1", ('REF%d' % uid,)).fetchone()
    con.commit()
    con.close()
    left = (my['max_uses'] - my['used']) if my else 0
    head = ('ссылка активна — отправь её тому, кому нужен бот' if bought
            else 'ссылка откроется после первой покупки: сделай заказ, и код заработает')
    tail = ('твой купон: <code>%s</code> — минус 10%% на следующий заказ' % my['code']) if left > 0 else 'за каждого, кто по ссылке оплатит — минус 10% на твой следующий заказ'
    return ('<b>РЕФЕРАЛЬНЫЙ КОД</b>\n\n%s\n\nкод: <code>ref%s</code>\nссылка: <code>%s</code>\n\n'
            'пришло по ссылке: %d\nоплатили: %d\n\n%s') % (head, uid, ref_link(uid), inv, paid, tail)


async def ref_reward_sweep(client):
    con = db()
    rows = con.execute(
        "select b.uid, b.ref_by from botleads b where b.ref_by > 0 and coalesce(b.ref_paid,0) = 0 "
        "and exists (select 1 from orders o where o.client_id = b.uid and o.status <> 'new' and coalesce(o.note,'') <> 'demo') "
        "and exists (select 1 from orders o2 where o2.client_id = b.ref_by and o2.status <> 'new' and coalesce(o2.note,'') <> 'demo')").fetchall()
    n = 0
    for r in rows:
        rid = r['ref_by']
        code = 'REF%d' % rid
        until = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(timespec='seconds')
        cur = con.execute("select max_uses from coupons where code=?", (code,)).fetchone()
        if cur:
            con.execute("update coupons set max_uses = max_uses + 1, active = 1, until = ? where code=?", (until, code))
        else:
            con.execute("insert into coupons (code, percent, amount_off, max_uses, used, active, until, promo) values (?,10,0,1,0,1,?,0)", (code, until))
        con.execute("update botleads set ref_paid = 1 where uid=?", (r['uid'],))
        con.commit()
        n += 1
        try:
            await client.send_message(rid, 'по твоей ссылке оплатили. купон <code>%s</code> — минус 10%% на следующий заказ, действует 30 дней.' % code)
        except Exception as ex:
            print('ref notify', type(ex).__name__, ex)
    con.close()
    if n:
        print('ref rewards:', n, flush=True)
    return n

def err_ru(ex):
    n = type(ex).__name__
    if n == 'ChatAdminRequiredError':
        return 'участники скрыты, нужен админ чата'
    if n == 'ChannelPrivateError':
        return 'приватный чат, нужен доступ'
    if n == 'FloodWaitError':
        return 'лимит Telegram, повторю позже'
    if n in ('UsernameNotOccupiedError', 'UsernameInvalidError', 'ValueError'):
        return 'не вижу чат: либо нет такого, либо парсер не в нём'
    return n


async def probe_chat(link):
    try:
        ent = await USER.get_entity(link)
    except Exception as ex:
        return 'недоступен (%s)' % err_ru(ex)
    try:
        n = await USER.get_participants(ent, limit=100)
        return 'ок, видно участников: %d' % len(n)
    except Exception as ex:
        if 'ChatAdminRequired' in type(ex).__name__:
            try:
                n = await USER.get_participants(ent, limit=100, aggressive=True)
                return 'ок, скрытый список обошли: %d' % len(n)
            except Exception as ex2:
                return 'участники скрыты (%s)' % err_ru(ex2)
        return 'участников не видно (%s)' % err_ru(ex)


def seed_chats():
    con = db()
    con.execute("create table if not exists chats (cat text, link text, added text, status text, primary key (cat, link))")
    if not con.execute("select count(*) from chats").fetchone()[0]:
        t = now_iso()
        for cat, pair in BASE_CATS.items():
            for l in pair[1]:
                con.execute("insert or ignore into chats (cat, link, added, status) values (?,?,?,'')", (cat, l, t))
    con.commit()
    con.close()


def cat_links(cat):
    con = db()
    rows = con.execute("select link from chats where cat=? order by link", (cat,)).fetchall()
    con.close()
    return [r['link'] for r in rows]


async def find_chats(q, limit=20):
    try:
        res = await USER(tl_functions.contacts.SearchRequest(q=q, limit=limit))
    except Exception as ex:
        return ['ошибка поиска: %s' % err_ru(ex)]
    out = []
    for c in res.chats:
        u = getattr(c, 'username', None)
        if not u:
            continue
        out.append(('@' + u, getattr(c, 'title', '') or '', getattr(c, 'participants_count', None)))
    return out


EXTRA = {
    'crypto': ['биткоин', 'трейдинг'],
    'freelance': ['удаленка', 'заказы'],
    'hr': ['вакансии', 'резюме'],
    'smm': ['таргет', 'маркетинг'],
    'market': ['wildberries', 'селлеры'],
    'infobiz': ['продюсер', 'эксперты'],
    'dating': ['дейтинг', 'любовь'],
    'gamble': ['казино', 'беттинг'],
}


async def pick_parseable(res):
    if not res:
        return [], 0
    sts = []
    for k in range(0, len(res), 4):
        chunk = res[k:k + 4]
        got = await asyncio.gather(*[asyncio.wait_for(probe_parse(u), 10) for u, t, n in chunk], return_exceptions=True)
        sts.extend(got)
    ok = []
    bad = 0
    for (u, t, n), pst in zip(res, sts):
        if isinstance(pst, Exception):
            pst = (False, 'ошибка')
        if pst[0]:
            ok.append((u, t, n, pst[1]))
        else:
            bad += 1
    return ok, bad



async def find_send(e, q, cat=''):
    print('find start', q, cat, flush=True)
    try:
        print('user conn', bool(USER), USER.is_connected() if USER else False, flush=True)
    except Exception as ex:
        print('user info fail', ex, flush=True)
    await e.respond('ищу и проверяю чаты, пару секунд...')
    try:
        res = await asyncio.wait_for(find_chats(q), timeout=15)
        print('find searched', len(res), flush=True)
    except Exception as ex:
        print('find timeout', type(ex).__name__, flush=True)
        await e.respond('поиск не ответил: %s' % type(ex).__name__)
        return
    print('find searched', len(res), flush=True)
    if res and isinstance(res[0], str):
        await e.respond('\n'.join(res))
        return
    ok, bad = await pick_parseable(res[:8] if res else [])
    words = list(EXTRA.get(cat, []))
    used = []
    while not ok and words:
        w = words.pop(0)
        used.append(w)
        try:
            r2 = await asyncio.wait_for(find_chats(w), timeout=20)
        except Exception:
            continue
        if r2 and isinstance(r2[0], str):
            continue
        ok, bad2 = await pick_parseable(r2[:6])
        bad += bad2
    if not ok:
        await e.respond('годных чатов не нашлось. попробуй другую вертикаль или напиши слово: /find работа')
        return
    kb = [[Button.inline(btn_label(u, t), (('fa:%s:%s' % (cat, u)) if cat else ('fp:%s' % u)).encode())] for u, t, n, _ in ok]
    out = ['<b>ГОДНЫХ %d</b>%s' % (len(ok), (' · отсеяно %d' % bad) if bad else ''), '']
    for u, t, n, txt in ok:
        out.append('%s%s — %s' % (u, (' · %s участников' % n) if n else '', txt))
    if used:
        out.append('')
        out.append('искал также: ' + ', '.join(used))
    print('find respond', flush=True)
    print('kb', len(kb), flush=True)
    try:
        await e.respond('\n'.join(out), buttons=kb)
    except Exception as ex:
        await e.respond('кнопки не прошли (%s)\n\n%s' % (type(ex).__name__, '\n'.join(u for u, t, n, _ in ok)))

async def join_chat(link):
    link = (link or '').strip()
    try:
        if '/+' in link or 'joinchat' in link:
            h = link.rstrip('/').split('/')[-1].lstrip('+')
            await USER(tl_functions.messages.ImportChatInviteRequest(h))
            return 'вошёл по ссылке'
        ent = await USER.get_entity(link)
        await USER(tl_functions.channels.JoinChannelRequest(ent))
        return 'вошёл'
    except Exception as ex:
        if 'AlreadyParticipant' in type(ex).__name__:
            return 'уже внутри'
        return 'не смог (%s)' % err_ru(ex)


BUILD_LIMIT = int(os.getenv('BUILD_LIMIT', '3000'))

BASE_CATS = {
    'crypto': ('крипта и арбитраж', ['@cryptocurrencytalk', '@crypto_ru', '@bitcoin_ru']),
    'freelance': ('фриланс и удалёнка', ['@freelancechat', '@work_ru', '@freelance_ru']),
    'hr': ('вакансии и HR', ['@hr_ru', '@vacancy_ru', '@rabota_ru']),
    'smm': ('SMM и таргет', ['@smm_ru', '@smmchat', '@target_ru']),
    'market': ('маркетплейсы и дропшип', ['@marketplace_ru', '@dropshipping_ru', '@wb_sellers']),
    'infobiz': ('инфобиз и продюсеры', ['@infobiz_ru', '@producer_ru', '@experts_ru']),
    'dating': ('дейтинг и знакомства', ['@dating_ru', '@znakomstva_ru', '@love_ru']),
    'gamble': ('ставки и казино', ['@betting_ru', '@casino_ru', '@stavki_ru']),
}


SEARCH = {
    'crypto': 'крипта',
    'freelance': 'фриланс',
    'hr': 'работа',
    'smm': 'смм',
    'market': 'маркетплейс',
    'infobiz': 'инфобиз',
    'dating': 'знакомства',
    'gamble': 'ставки',
}


def cat_kb():
    cats = sorted(BASE_CATS)
    rows = [cats[k:k + 2] for k in range(0, len(cats), 2)]
    return [[Button.inline(SEARCH.get(c, c), ('fq:%s' % c).encode()) for c in r] for r in rows]


def person_ok(u):
    if getattr(u, 'bot', False) or getattr(u, 'deleted', False):
        return False
    if getattr(u, 'scam', False) or getattr(u, 'fake', False):
        return False
    if not (u.first_name or '').strip():
        return False
    return bool(u.username) and nick_ok(u.username)


async def quick_report(link, limit=300):
    try:
        ent, title, users, scan, bots, deleted = await parse_chat(link, limit)
    except Exception as ex:
        return 0, 0, 'не смог прочитать: %s' % err_ru(ex)
    live = [u for u in users if person_ok(u)]
    prem = [u for u in live if getattr(u, 'premium', False)]
    photo = sum(1 for u in live if getattr(u, 'photo', None))
    rep = ('чат: %s\nпроверено: %d\nживых людей: %d\nпремиум: %d\nс фото: %d'
           % (title, scan, len(live), len(prem), photo))
    return len(live), len(prem), rep


RATE_LIVE = float(os.getenv('RATE_LIVE', '4'))
RATE_PREMIUM = float(os.getenv('RATE_PREMIUM', '8'))
MIN_PRICE = float(os.getenv('MIN_PRICE', '3'))


def price_for(kind, qty):
    rate = RATE_PREMIUM if kind == 'prem' else RATE_LIVE
    return round(max(MIN_PRICE, rate * (max(1, qty) / 1000.0)), 2)


async def deliver_dyn(client, uid):
    con = db()
    r = con.execute("select note from orders where client_id=? and product like 'dyn%' order by id desc limit 1", (uid,)).fetchone()
    con.close()
    note = (r['note'] if r else '') or ''
    parts = note.split('|')
    if len(parts) < 4:
        await client.send_message(uid, 'не нашёл параметры заказа — пришли ссылку на чат ещё раз')
        return 0
    kind, cat, qty, link = parts[0], parts[1], int(parts[2] or 0), parts[3]
    return await send_base(client, uid, link, qty, note='\n\n(%s, %d шт)' % ('премиум' if kind == 'prem' else 'живые', qty), kind=kind)


def nick_ok(n):
    n = n or ''
    if len(n) < 5 or len(n) > 32:
        return False
    if not re.match(r'^[A-Za-z0-9_]+$', n):
        return False
    if n.startswith('_') or n.endswith('_'):
        return False
    if re.search(r'\d{6,}', n):
        return False
    if n.lower().endswith('bot'):
        return False
    return True


async def build_category(cat):
    cat = (cat or '').strip().lower()
    if cat not in BASE_CATS:
        return 'нет такой категории. есть: ' + ', '.join(sorted(BASE_CATS))
    con = db()
    rows = con.execute("select link, status from chats where cat=? order by link", (cat,)).fetchall()
    con.close()
    good = [r['link'] for r in rows if (r['status'] or '').startswith('ок')]
    links = good or [r['link'] for r in rows]
    if not links:
        return 'нет чатов в категории %s. добавь: /add %s @chat' % (cat, cat)
    name = BASE_CATS[cat][0]
    rows2 = []
    rep = []
    for link in links:
        try:
            ent, title, users, scan, bots, deleted = await parse_chat(link, BUILD_LIMIT)
            rows2.extend(users)
            rep.append('%s: %d' % (title, len(users)))
        except Exception as ex:
            rep.append('%s: %s' % (link, err_ru(ex)))
    seen = set()
    clean = []
    for u in rows2:
        k = (u.username or '').lower()
        if not k or k in seen or not nick_ok(u.username):
            continue
        seen.add(k)
        clean.append(u)
    clean.sort(key=lambda u: (u.username or '').lower())
    premium = [u for u in clean if (u.first_name or '').strip() and (u.last_name or '').strip()]
    d = os.path.join('bases', cat)
    os.makedirs(d, exist_ok=True)
    for tier, arr in (('premium', premium), ('core', clean), ('1000', clean[:1000])):
        write_base(os.path.join(d, '%s_%s.csv' % (cat, tier)), arr)
        write_clean(os.path.join(d, '%s_%s.txt' % (cat, tier)), arr)
    passport = ('ПАСПОРТ БАЗЫ\nкатегория: %s\nсобрано: %s UTC\nисточники (%d):\n%s\n\n'
                'проверено всего: %d\nпосле чистки: %d\nпремиум (имя и фамилия): %d\nсрез 1000: %d\n\n'
                'ЧИСТКА\n- только @ники, дедуп по нику\n- отсев ботов и удалённых\n'
                '- ник 5-32 символа, латиница, цифры, подчёркивание\n'
                '- отсев ников с 6+ цифрами подряд и на _ в конце\n- сортировка по алфавиту\n\n'
                'ФАЙЛЫ\n%s_premium.csv / .txt\n%s_core.csv / .txt\n%s_1000.csv / .txt\n\n'
                'ФОРМАТ CSV: id;username;first_name;last_name;phone\n'
                'кодировка UTF-8 BOM, разделитель ; — открывается в Excel двойным кликом\n'
                'TXT: по одному @нику в строке, для рассылки\n\n'
                'ГАРАНТИЯ\nесли ники мёртвые — меняем или дополняем\n'
                ) % (name, now_iso()[:16], len(links), '\n'.join('  ' + r for r in rep),
                     len(rows2), len(clean), len(premium), min(1000, len(clean)), cat, cat, cat)
    open(os.path.join(d, '%s_PASSPORT.txt' % cat), 'w', encoding='utf-8').write(passport)
    print('build', cat, 'clean', len(clean), 'premium', len(premium), flush=True)
    return passport


def card_kb(code, price, has_demo):
    row = []
    if has_demo:
        row.append(Button.inline('пример', ('o:' + code).encode()))
    row.append(Button.inline('заказать · %g' % price, b'buy'))
    return [row, [Button.inline('назад в меню', b'menu')]]

DEMOS = ('botparser', 'botkassa', 'botzapis', 'botquiz', 'botreply')

async def run_demo(client, e, uid, st, code, arg):
    save_lead(uid, interest=code, demo=True)
    if code == 'botparser':
        st['await'] = 'parse_link'
        await e.edit('<b>ПОПРОБУЙ ПАРСЕР</b>\n\nпришли ссылку или @ник любого чата — спарсю до 100 участников и пришлю файл.\n\nэто честное демо, работаю по-настоящему.', buttons=back_kb())
        return
    if code == 'botkassa':
        if arg == 'go':
            kb = [[Button.inline('шапка — 15', b'dm:botkassa:b1')],
                  [Button.inline('футболка — 20', b'dm:botkassa:b2')],
                  [Button.inline('назад в меню', b'menu')]]
            await e.edit('<b>ВИТРИНА (демо)</b>\n\nтак выглядит магазин внутри бота. нажми любой товар.', buttons=kb)
            return
        item = 'шапка' if arg == 'b1' else 'футболка'
        amount = 15 if arg == 'b1' else 20
        kb = [[Button.inline('оплатить %d' % amount, ('dm:botkassa:pay' + arg[-1]).encode())],
              [Button.inline('назад в меню', b'menu')]]
        await e.edit('<b>%s — %d</b>\n\nтак выглядит карточка товара. дальше бот берёт оплату и сам отдаёт файл.' % (item.upper(), amount), buttons=kb)
        return
    if code == 'botkassa' and arg.startswith('pay'):
        con = db()
        con.execute("insert into orders (client_id, product, qty, amount, coupon, invoice_id, status, created_at, note) values (?,?,?,?,?,?,?,?,?)", (uid, 'demo_kassa', 1, 0, '', '', 'demo', now_iso(), 'demo'))
        con.commit()
        n_demo = con.execute("select count(*) from orders where note='demo'").fetchone()[0]
        con.close()
        txt = '<b>ОПЛАТА ПРОШЛА (демо)</b>\n\nвот так покупатель получает товар сразу после оплаты — файлом, без тебя.\n\nзаказ реально упал в базу, демо-заказов: %d' % n_demo
        await e.edit(txt, buttons=back_kb())
        path = os.path.join(OUT, 'demo_tovar.txt')
        os.makedirs(OUT, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('это пример товара, который бот выдаёт после оплаты\n')
        try:
            await client.send_file(uid, path, caption='файл выдан автоматически')
        except Exception:
            pass
        return
    if code == 'botzapis':
        if arg == 'go':
            kb = [[Button.inline('сегодня 15:00', b'dm:botzapis:s1')],
                  [Button.inline('сегодня 18:00', b'dm:botzapis:s2')],
                  [Button.inline('завтра 12:00', b'dm:botzapis:s3')],
                  [Button.inline('назад в меню', b'menu')]]
            await e.edit('<b>ЗАПИСЬ (демо)</b>\n\nтак клиент выбирает время. выбери слот.', buttons=kb)
            return
        slot = {'s1': 'сегодня 15:00', 's2': 'сегодня 18:00', 's3': 'завтра 12:00'}.get(arg, '')
        con = db()
        con.execute("insert into slots (uid, slot, created_at) values (?,?,?)", (uid, slot, now_iso()))
        con.commit()
        mine = [r[0] for r in con.execute("select slot from slots where uid=? order by id", (uid,)).fetchall()]
        con.close()
        await e.edit('<b>ЗАПИСЬ ПОДТВЕРЖДЕНА (демо)</b>\n\nслот: %s\n\nзапись реально сохранена. все твои записи: %s' % (slot, ', '.join(mine)), buttons=back_kb())
        return
    if code == 'botquiz':
        if arg == 'go':
            kb = [[Button.inline('до 50к', b'dm:botquiz:q1a')], [Button.inline('50-200к', b'dm:botquiz:q1b')], [Button.inline('назад в меню', b'menu')]]
            await e.edit('<b>КВИЗ (демо), вопрос 1 из 2</b>\n\nкакой у тебя бюджет на рекламу в месяц?', buttons=kb)
            return
        if arg.startswith('q1'):
            con = db()
            con.execute("insert or ignore into demo_quiz (uid, updated_at) values (?,?)", (uid, now_iso()))
            con.execute("update demo_quiz set budget=?, updated_at=? where uid=?", (arg, now_iso(), uid))
            con.commit()
            con.close()
            kb = [[Button.inline('да', b'dm:botquiz:q2a')], [Button.inline('нет', b'dm:botquiz:q2b')], [Button.inline('назад в меню', b'menu')]]
            await e.edit('<b>ВОПРОС 2 ИЗ 2</b>\n\nуже пробовал рассылку по чатам?', buttons=kb)
            return
        con = db()
        con.execute("insert or ignore into demo_quiz (uid, updated_at) values (?,?)", (uid, now_iso()))
        con.execute("update demo_quiz set rassylka=?, updated_at=? where uid=?", (arg, now_iso(), uid))
        con.commit()
        con.close()
        st['await'] = 'quiz_nick'
        await e.edit('<b>ПОЧТИ ВСЁ (демо)</b>\n\nнапиши свой @ник — бот сохранит контакт и пришлёт лид-магнит. так он собирает заявки.', buttons=back_kb())
        return
    if code == 'botreply':
        st['await'] = 'reply_test'
        await e.edit('<b>АВТООТВЕТЧИК (демо)</b>\n\nнапиши что угодно — отвечу по скрипту. например: сколько стоит?', buttons=back_kb())
        return

try:
    from telethon.errors import FloodWaitError
except Exception:
    FloodWaitError = Exception

DEMO_LIMIT = int(os.getenv('DEMO_LIMIT', '100'))
PARSE_LIMIT = int(os.getenv('PARSE_LIMIT', '10000'))


async def parse_chat(link, limit):
    ent = await USER.get_entity(link)
    title = getattr(ent, 'title', None) or str(link)
    rows, scan, bots, deleted = [], 0, 0, 0
    for agg in (True, False, True):
        rows, seen_u, seen_i = [], set(), set()
        scan = bots = deleted = 0
        try:
            async for u in USER.iter_participants(ent, aggressive=agg):
                scan += 1
                if getattr(u, 'bot', False):
                    bots += 1
                    continue
                if getattr(u, 'deleted', False):
                    deleted += 1
                    continue
                if u.username:
                    k = u.username.lower()
                    if k in seen_u:
                        continue
                    seen_u.add(k)
                else:
                    if u.id in seen_i:
                        continue
                    seen_i.add(u.id)
                rows.append(u)
                if len(rows) >= limit:
                    break
            if rows:
                break
        except FloodWaitError as ex:
            await asyncio.sleep(min(getattr(ex, 'seconds', 30), 90) + 2)
        except Exception:
            pass
    rows.sort(key=lambda u: (0 if u.username else 1, (u.username or '').lower()))
    return ent, title, rows, scan, bots, deleted

def write_base(path, rows):
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['id', 'username', 'first_name', 'last_name', 'phone'])
        for u in rows:
            w.writerow([u.id, ('@' + u.username) if u.username else '', u.first_name or '', u.last_name or '', u.phone or ''])
    return len(rows)


def write_clean(path, rows):
    n = 0
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        for u in rows:
            if u.username:
                f.write('@%s\n' % u.username)
                n += 1
    return n


async def send_base(client, uid, link, limit, note='', kind='live'):
    if not link:
        link = (STATE.get(uid) or {}).get('chat', '')
    if not link:
        await client.send_message(uid, 'не нашёл ссылку на чат. пришли её ещё раз — соберу базу сразу')
        return 0
    os.makedirs(OUT, exist_ok=True)
    try:
        ent, title, rows, scan, bots, deleted = await parse_chat(link, limit if kind == 'live' else min(PARSE_LIMIT, max(limit * 5, 1000)))
    except Exception as ex:
        await client.send_message(uid, 'не смог прочитать этот чат: %s\n\nварианты:\n1) добавить наш аккаунт админом — список участников откроется\n2) дать другую ссылку' % err_ru(ex))
        raise
    full = os.path.join(OUT, 'base_%s.csv' % uid)
    clean = os.path.join(OUT, 'nicks_%s.txt' % uid)
    rows = [u for u in rows if person_ok(u)]
    if kind == 'prem':
        rows = [u for u in rows if getattr(u, 'premium', False)]
    rows = rows[:limit]
    n_full = write_base(full, rows)
    n_clean = write_clean(clean, rows)
    with_phone = sum(1 for u in rows if u.phone)
    cap = ('<b>ГОТОВО</b>\n\nчат: %s\nпроверено: %d\nв базе: %d\nс ником: %d\nс телефоном: %d\nботов отсеяно: %d%s\n\n'
           'файл 1 — таблица для Excel\nфайл 2 — только ники для рассылки' % (title, scan, n_full, n_clean, with_phone, bots, note))
    await client.send_file(uid, full, caption=cap)
    if n_clean:
        await client.send_file(uid, clean, caption='чистый список ников: %d' % n_clean)
    print('base', uid, 'rows', n_full, 'scan', scan, flush=True)
    return n_full


async def parse_and_send(client, uid, link, note=''):
    return await send_base(client, uid, link, DEMO_LIMIT, note)



CAPTION = (
    '<b>HUNTER PAY</b>\n'
    'готовые боты для Telegram — забираешь за день\n\n'
    'Парсер, касса, запись, квиз, автоответчик. Не «сделаем под вас», а уже работающие вещи: выбираешь, пробуешь и только потом платишь.\n\n'
    '<b>Что внутри</b>\n'
    '• парсер — кидаешь ссылку на чат, получаешь базу файлом\n'
    '• касса — витрина, оплата и автовыдача товара\n'
    '• запись — клиент сам выбирает свободный слот\n'
    '• квиз — воронка, которая собирает заявки\n'
    '• автоответчик — отвечает первым, круглосуточно\n\n'
    '<b>Почему у меня</b>\n'
    'У каждого бота есть демо — жми «пример» и смотри, как бот работает, ещё до оплаты. у парсера демо настоящее: присылаешь свой чат — получаешь файл. Никаких скриншотов и обещаний.\n'
    'Срок — 1 день. У фрилансера это две недели и 30–75.\n\n'
    'Не знаешь, что выбрать — жми «о боте», там всё разложено.\n\n'
    'Выбирай ↓'
)

ABOUT = (
    '<b>ЧТО ЗДЕСЬ ПРОИСХОДИТ</b>\n\n'
    'Делаю готовых ботов под конкретную задачу. Не конструктор и не «настроите сами» — рабочий бот с твоей логикой, который запускается за день.\n\n'
    '<b>ЧТО МОЖНО ЗАБРАТЬ</b>\n'
    '• <b>Парсер</b> — кидаешь ссылку на чат, бот отдаёт базу: ник, id, имя, телефон где есть. Боты и дубли вычищены.\n'
    '• <b>Касса</b> — витрина товаров внутри бота, приём оплаты, автовыдача файла после оплаты, список покупателей.\n'
    '• <b>Запись</b> — клиент сам выбирает свободный слот, получает подтверждение и напоминание.\n'
    '• <b>Квиз</b> — воронка из вопросов: собирает контакт, отдаёт лид-магнит, тебе падает уведомление.\n'
    '• <b>Автоответчик</b> — отвечает первым на входящие, держит скрипт, зовёт тебя в диалог.\n\n'
    '<b>КАК ЭТО РАБОТАЕТ</b>\n'
    '1. Смотришь демо прямо здесь, бесплатно.\n'
    '2. Нажимаешь «заказать» — приходит счёт в USDT.\n'
    '3. Через день получаешь бота и команду установки в одну строку.\n\n'
    '<b>ЧТО НУЖНО ОТ ТЕБЯ</b>\n'
    'Только задача и токен от @BotFather. Всё остальное моя работа. Разверну на бесплатном хостинге у тебя — или буду держать у себя по подписке.\n\n'
    '<b>ЦЕНЫ</b>\n'
    'бот под ключ — 59, автоответчик — 49, доработка под твою логику — +30\n'
    'базы от 5, чистка базы 10, рассылка по 1000 живым 30\n\n'
    'Нужного бота нет в списке? Напиши задачу — скажу цену и срок.'
)

SHORT = 'Боты для Telegram под твою задачу. Демо до оплаты, готовлю за день.'

DESC = ('HUNTER PAY — готовые боты для Telegram.\n\n'
        'Парсер, касса, запись, квиз, автоответчик. Не «сделаем под вас», а уже работающие вещи: '
        'потыкай демо бесплатно и только потом платишь.\n\n'
        '• бот под ключ — за 1 день\n'
        '• демо у каждого, без предоплаты\n'
        '• у фрилансера это две недели и 30–75\n\n'
        'Базы участников чатов и чистка — от 5.\n\n'
        'Нажми «Запустить бота» ↓')


def set_commands():
    base = 'https://api.telegram.org/bot%s/' % BOT_TOKEN
    cmds = [{"command": "start", "description": "витрина и меню"},
            {"command": "about", "description": "о боте"},
            {"command": "help", "description": "написать человеку"},
            {"command": "leads", "description": "лиды бота"}]
    def call(method, payload):
        req = urllib.request.Request(base + method, data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                print(method, r.status)
        except Exception as ex:
            print(method, 'FAIL', ex)
    call('setMyCommands', {"commands": cmds})
    call('setChatMenuButton', {"menu_button": {"type": "commands"}})
    call('setMyDescription', {"description": DESC})
    call('setMyShortDescription', {"short_description": SHORT})


def lead_init():
    con = db()
    con.execute("create table if not exists botleads (uid integer primary key, username text, name text, phone text, src text, first_seen text, last_seen text, interest text, demo integer default 0, orders integer default 0)")
    con.execute("create table if not exists slots (id integer primary key autoincrement, uid integer, slot text, created_at text)")
    con.execute("create table if not exists demo_quiz (uid integer primary key, budget text, rassylka text, nick text, updated_at text)")
    for ddl in ("alter table coupons add column until text",
                "alter table coupons add column promo integer default 0",
                "alter table botleads add column coupon_sent integer default 0",
                "alter table botleads add column ref_by integer",
                "alter table botleads add column ref_paid integer default 0"):
        try:
            con.execute(ddl)
        except Exception:
            pass
    if not con.execute("select code from coupons where code='START'").fetchone():
        until = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(timespec='seconds')
        con.execute("insert into coupons (code, percent, amount_off, max_uses, used, active, until, promo) values ('START',10,0,50,0,1,?,1)", (until,))
        print('privetstvennyy kupon START sozdan do', until[:16])
    con.commit()
    con.close()


def save_lead(uid, username=None, name=None, src=None, interest=None, demo=False, order=False):
    con = db()
    t = now_iso()
    con.execute("insert or ignore into botleads (uid, first_seen, last_seen, interest, demo, orders) values (?,?,?,'',0,0)", (uid, t, t))
    if username:
        con.execute("update botleads set username=? where uid=?", (username, uid))
    if name:
        con.execute("update botleads set name=? where uid=?", (name, uid))
    if src:
        con.execute("update botleads set src=? where uid=? and (src is null or src='')", (src, uid))
    if interest:
        r = con.execute("select interest from botleads where uid=?", (uid,)).fetchone()
        cur = (r['interest'] or '') if r else ''
        if interest not in cur.split(','):
            con.execute("update botleads set interest=? where uid=?", ((cur + ',' + interest).strip(','), uid))
    if demo:
        con.execute("update botleads set demo = demo + 1 where uid=?", (uid,))
    if order:
        con.execute("update botleads set orders = orders + 1 where uid=?", (uid,))
    con.execute("update botleads set last_seen=? where uid=?", (t, uid))
    con.commit()
    con.close()


async def main():
    seed()
    lead_init()
    global USER
    client = TelegramClient(SESSION, API_ID, API_HASH)
    client.parse_mode = 'html'
    await client.start(bot_token=BOT_TOKEN)
    me = await client.get_me()
    print('vitrina zapushchena:', me.username)
    set_commands()

    USER = TelegramClient(USERSESSION, API_ID, API_HASH)
    try:
        await USER.connect()
        if not await USER.is_user_authorized():
            print('parser demo OFF: user session ne avtorizovana')
            USER = None
    except Exception as ex:
        print('parser demo OFF:', ex)
        USER = None

    async def show_menu(uid, edit=None, note=''):
        txt = CAPTION
        if note:
            txt += chr(10) + chr(10) + note
        kb = menu_kb()
        if edit:
            try:
                await edit.edit(txt, buttons=kb)
            except Exception:
                pass
        elif os.path.exists(PHOTO):
            await client.send_file(uid, PHOTO, caption=txt, buttons=kb)
        else:
            await client.send_message(uid, txt, buttons=kb)

    @client.on(events.NewMessage())
    async def msg(e):
        if not e.sender_id:
            return
        uid = e.sender_id
        txt = (e.raw_text or '').strip()
        print("msg", uid, repr(txt)[:70], flush=True)
        st = STATE.setdefault(uid, {})
        try:
            _s = await e.get_sender()
            _n = ' '.join([x for x in [getattr(_s, 'first_name', None), getattr(_s, 'last_name', None)] if x])
            save_lead(uid, getattr(_s, 'username', None), _n)
        except Exception:
            save_lead(uid)
        if e.photo and uid == OWNER:
            os.makedirs('assets', exist_ok=True)
            await e.download_media(PHOTO)
            await e.respond('баннер сохранён')
            return
        act = getattr(e.message, 'action', None)
        if act is not None and hasattr(act, 'payload'):
            await paid_stars(uid, act.payload)
            return
        if uid == OWNER and txt.startswith('/cup'):
            args = txt.split()
            con = db()
            if len(args) >= 5 and args[1] == 'new':
                code = args[2].upper()
                pct = float(args[3]); mx = int(args[4]); days = int(args[5]) if len(args) > 5 else 7
                until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(timespec='seconds')
                con.execute("insert or replace into coupons (code, percent, amount_off, max_uses, used, active, until, promo) values (?,?,0,?,0,1,?,1)", (code, pct, mx, until))
                con.commit()
                await client.send_message(uid, 'купон <code>%s</code>: минус %g%%, лимит %d, до %s' % (code, pct, mx, until[:16].replace('T', ' ')))
            elif len(args) >= 3 and args[1] == 'off':
                con.execute("update coupons set active=0 where code=?", (args[2].upper(),))
                con.commit()
                await client.send_message(uid, 'купон %s выключен' % args[2].upper())
            else:
                rows = con.execute("select code, percent, amount_off, max_uses, used, active, until from coupons order by code limit 20").fetchall()
                lines = ['<b>КУПОНЫ</b>', '']
                for r in rows:
                    lines.append('%s | %s | лимит %s | исп. %s | %s | до %s' % (r['code'], disc_text(r), r['max_uses'], r['used'], 'ON' if r['active'] else 'OFF', (r['until'] or '-')[:16].replace('T', ' ')))
                lines.append('')
                lines.append('/cup new КОД 10 50 7 — создать')
                lines.append('/cup off КОД')
                await client.send_message(uid, chr(10).join(lines))
            con.close()
            return
        if uid == OWNER and txt.startswith('/push'):
            text = txt[5:].strip()
            if not text:
                await client.send_message(uid, 'напиши так: /push текст')
                return
            con = db()
            rows = con.execute("select uid from botleads where uid <> ? order by last_seen desc", (OWNER,)).fetchall()
            con.close()
            await client.send_message(uid, 'рассылаю %d лидам...' % len(rows))
            ok = 0
            for r in rows:
                try:
                    await client.send_message(r['uid'], text)
                    ok += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            await client.send_message(uid, 'готово, дошло до %d из %d' % (ok, len(rows)))
            return
        if uid == OWNER and txt.startswith('/leadscsv'):
            p = os.path.join(OUT, 'botleads.csv')
            os.makedirs(OUT, exist_ok=True)
            con = db()
            rows = con.execute("select uid, username, name, phone, src, first_seen, last_seen, interest, demo, orders from botleads order by first_seen").fetchall()
            con.close()
            with open(p, 'w', encoding='utf-8', newline='') as f:
                w = csv.writer(f)
                w.writerow(['uid', 'username', 'name', 'phone', 'src', 'first_seen', 'last_seen', 'interest', 'demo', 'orders'])
                for r in rows:
                    w.writerow([r[k] for k in r.keys()])
            await client.send_file(uid, p, caption='лидов: %d' % len(rows))
            return
        if uid == OWNER and txt.startswith('/leads'):
            con = db()
            n = con.execute('select count(*) from botleads').fetchone()[0]
            d = con.execute('select count(*) from botleads where demo > 0').fetchone()[0]
            o = con.execute('select count(*) from botleads where orders > 0').fetchone()[0]
            rows = con.execute("select uid, username, name, phone, interest, last_seen, demo, orders from botleads order by last_seen desc limit 40").fetchall()
            con.close()
            lines = ['<b>ЛИДОВ: %d</b> · жали демо: %d · заказов: %d' % (n, d, o), '']
            for r in rows:
                lines.append('@%s %s | %s | %s | демо %d | заказ %d' % (r['username'] or r['uid'], r['name'] or '', r['interest'] or '-', (r['last_seen'] or '')[5:16], r['demo'], r['orders']))
            await client.send_message(uid, chr(10).join(lines))
            return
        if txt.startswith('/about'):
            await client.send_message(uid, ABOUT, buttons=back_kb())
            return
        if txt.startswith('/help'):
            await e.respond('напиши задачу прямо сюда — отвечу и скажу цену и срок')
            return
        if txt.startswith('/start'):
            parts = txt.split()
            if len(parts) > 1 and parts[1].startswith('ref'):
                try:
                    rid = int(parts[1][3:])
                except Exception:
                    rid = 0
                if rid and rid != uid:
                    con = db()
                    con.execute("update botleads set ref_by=? where uid=?", (rid, uid))
                    con.commit()
                    con.close()
            parts = txt.split()
            if len(parts) > 1:
                cop = coupon(parts[1])
                st['coupon'] = cop['code'] if cop else ''
                save_lead(uid, src=parts[1])
            if not st.get('coupon'):
                if coupon('START'):
                    st['coupon'] = 'START'
            note = ''
            if st.get('coupon'):
                c = coupon(st['coupon'])
                if c:
                    note = 'купон <code>%s</code> принят: %s' % (c['code'], disc_text(c))
            await show_menu(uid, note=note)
            return
        if st.get('await') == 'find' and not txt.startswith('/'):
            st['await'] = ''
            try:
                await find_send(e, txt)
            except Exception as ex:
                await e.respond('сбой поиска: %s %s' % (type(ex).__name__, ex))
            return
        if txt.startswith('/find'):
            if uid not in ADMINS:
                return
            w = txt.split()
            cat = ''
            q = txt[5:].strip()
            if len(w) > 1 and w[1].lower() in BASE_CATS:
                cat = w[1].lower()
                q = ' '.join(w[2:])
            if not q:
                await e.respond('<b>ВЫБЕРИ ВЕРТИКАЛЬ</b>\n\nили напиши слово: /find работа', buttons=cat_kb())
                return
            try:
                await find_send(e, q, cat)
            except Exception as ex:
                await e.respond('сбой поиска: %s %s' % (type(ex).__name__, ex))
            return
        if txt.startswith('/add'):
            if uid not in ADMINS:
                return
            w = txt.split()
            if len(w) < 3:
                await e.respond('напиши: /add crypto @chat')
                return
            con = db()
            con.execute("insert or ignore into chats (cat, link, added, status) values (?,?,?,'')", (w[1].lower(), w[2], now_iso()))
            con.commit()
            con.close()
            await e.respond('добавил %s в %s' % (w[2], w[1].lower()))
            return
        if txt.startswith('/del'):
            if uid not in ADMINS:
                return
            w = txt.split()
            if len(w) < 3:
                await e.respond('напиши: /del crypto @chat')
                return
            con = db()
            con.execute("delete from chats where cat=? and link=?", (w[1].lower(), w[2]))
            con.commit()
            con.close()
            await e.respond('убрал %s из %s' % (w[2], w[1].lower()))
            return
        if txt.startswith('/join'):
            if uid not in ADMINS:
                return
            w = txt.split()
            if len(w) > 1:
                await e.respond('%s — %s' % (w[1], await join_chat(w[1])))
                return
            con = db()
            links = [r['link'] for r in con.execute("select link from chats order by cat, link").fetchall()]
            con.close()
            out = []
            for l in links:
                out.append('%s — %s' % (l, await join_chat(l)))
                await asyncio.sleep(4)
            await e.respond('\n'.join(out)[:3500])
            return
        if txt.startswith('/probe'):
            if uid not in ADMINS:
                return
            w = txt.split()
            cats = [w[1].lower()] if len(w) > 1 else sorted(BASE_CATS)
            con = db()
            out = ['<b>ПРОВЕРКА ЧАТОВ</b>', '']
            for cat in cats:
                out.append('<b>%s</b>' % cat)
                for r in con.execute("select link from chats where cat=? order by link", (cat,)).fetchall():
                    stt = await probe_chat(r['link'])
                    con.execute("update chats set status=? where cat=? and link=?", (stt[:40], cat, r['link']))
                    out.append('  %s — %s' % (r['link'], stt))
            con.commit()
            con.close()
            await e.respond('\n'.join(out)[:3500])
            return
        if txt.startswith('/build'):
            if uid not in ADMINS:
                return
            w = txt.split()
            if len(w) < 2:
                out = ['<b>СБОРКА БАЗ</b>', '']
                for k in sorted(BASE_CATS):
                    d = os.path.join('bases', k)
                    n = len(os.listdir(d)) if os.path.isdir(d) else 0
                    out.append('%s — %s, чатов %d, файлов %d' % (k, BASE_CATS[k][0], len(cat_links(k)), n))
                out.append('')
                out.append('собрать: /build crypto')
                await e.respond('\n'.join(out))
                return
            cat = w[1].strip().lower()
            await e.respond('собираю %s, это пара минут...' % cat)
            try:
                await e.respond((await build_category(cat))[:3500])
            except Exception as ex:
                await e.respond('ошибка сборки: %s %s' % (type(ex).__name__, ex))
            return


        if st.get('await') == 'contact':
            st['await'] = ''
            con = db()
            con.execute("update botleads set phone=? where uid=?", (txt, uid))
            con.commit()
            con.close()
            await e.respond('записал: %s' % txt)
            if OWNER:
                await client.send_message(OWNER, 'НОВЫЙ КОНТАКТ: %s · uid %s' % (txt, uid))
            return
        if st.get('await') == 'coupon':
            st['await'] = ''
            cop = coupon(txt)
            if cop:
                st['coupon'] = cop['code']
                await show_menu(uid, note='купон <code>%s</code> принят, минус %d%%' % (cop['code'], cop['percent']))
            else:
                await show_menu(uid, note='такого купона нет, считаю по обычной цене')
            return
        if st.get('await') == 'quiz_nick':
            st['await'] = ''
            await e.respond('записал: %s\n\nтак бот собирает контакты. теперь «назад в меню» → «Бот-квиз» → «заказать».' % txt)
            return
        if st.get('await') == 'reply_test':
            t = txt.lower()
            if 'цен' in t or 'сколько' in t or 'стоим' in t:
                ans = 'добрый день! от 5 000, зависит от объёма. напишите задачу — посчитаю точно.'
            elif 'срок' in t or 'когда' in t:
                ans = 'обычно 1-2 дня. скиньте задачу, скажу точнее.'
            elif 'привет' in t or 'здравств' in t:
                ans = 'здравствуйте! слушаю вас, что нужно сделать?'
            else:
                ans = 'принял. уточню детали и вернусь с ценой.'
            await e.respond('<b>бот отвечает:</b>\n\n' + ans)
            return
        if st.get('await') == 'quiz_nick':
            st['await'] = ''
            con = db()
            con.execute("insert or ignore into demo_quiz (uid, updated_at) values (?,?)", (uid, now_iso()))
            con.execute("update demo_quiz set nick=? where uid=?", (txt.strip(), uid))
            con.commit()
            con.close()
            save_lead(uid, interest='botquiz')
            await e.respond('спасибо! ник сохранён, вот лид-магнит: короткий чек-лист по рассылке.\n\nтакой квиз соберёт тебе заявки в три касания.')
            return
        if st.get('await') == 'parse_link':
            st['await'] = ''
            if not USER:
                await e.respond('парсер сейчас не подключён, скажи об этом в чате')
                return
            await e.respond('парсю... до 100 участников, обычно меньше минуты')
            try:
                await parse_and_send(client, uid, txt.split()[0])
            except Exception as ex:
                print('parse fail', type(ex).__name__, ex)
                try:
                    await parse_and_send(client, uid, DEMO_CHAT, note='\n(по твоей ссылке состав скрыт, вот пример)')
                except Exception as ex2:
                    await e.respond('не смог разобрать эту ссылку: %s' % type(ex2).__name__)
            return
        if txt.startswith('/selftest') or txt.startswith('/pool'):
        return
    if txt.startswith('/selftest') or txt.startswith('/pool'):
        return
    if txt.startswith('/selftest') or txt.startswith('/pool'):
        return
    await e.respond('нажми /start. команды: /find, /add, /join, /probe, /build')

    @client.on(events.CallbackQuery())
    async def cb(e):
        uid = e.sender_id
        st = STATE.setdefault(uid, {})
        save_lead(uid)
        data = (e.data or b'').decode()
        print("cb", data, uid, flush=True)
        if data == 'menu':
            st['await'] = ''
            await show_menu(uid, edit=e)
            return
        if data == 'promo':
            con = db()
            rows = con.execute("select code, percent, amount_off, max_uses, used, until from coupons where active=1 and promo=1 order by code").fetchall()
            con.close()
            if not rows:
                await e.answer('акций сейчас нет', alert=True)
                return
            lines = ['<b>АКЦИИ</b>', '']
            for r in rows:
                left = (' · осталось %d' % max(0, r['max_uses'] - r['used'])) if r['max_uses'] else ''
                until = (' · до ' + r['until'][:16].replace('T', ' ')) if r['until'] else ''
                lines.append('<code>%s</code> — %s%s%s' % (r['code'], disc_text(r), left, until))
            lines.append('')
            lines.append('введи код кнопкой «купон» или открой ссылку с ним')
            await e.edit(chr(10).join(lines), buttons=back_kb())
            return
        if data == 'contact':
            st['await'] = 'contact'
            await e.edit('пришли телефон или @ник одним сообщением — сохраню и вернусь с предложением', buttons=back_kb())
            return
        if data == 'about':
            await e.answer()
            await client.send_message(uid, ABOUT, buttons=back_kb())
            return
        if data == 'noop':
            await e.answer()
            return
        if data == 'coupon':
            st['await'] = 'coupon'
            await e.edit('пришли код купона одним сообщением', buttons=back_kb())
            return
        if data == 'fqmenu':
            await e.edit('<b>ВЫБЕРИ ВЕРТИКАЛЬ</b>', buttons=cat_kb())
            return
        if data.startswith('fq:'):
            cat = data[3:]
            await e.answer('ищу в ' + cat)
            await find_send(e, SEARCH.get(cat, cat), cat)
            return
        if data.startswith('dq:'):
            _, cat, u, kind, qty = data.split(':', 4)
            qty = int(qty or 0)
            price = price_for(kind, qty)
            title = '%s %d из %s' % ('премиум' if kind == 'prem' else 'живые', qty, u)
            code = 'dyn_%d' % uid
            con = db()
            con.execute("insert or replace into products (code,title,descr,price,unit,delivery,active) values (?,?,?,?,?,?,0)",
                        (code, title, 'сборка по заказу', price, 'шт', 'dyn'))
            con.commit()
            con.close()
            st['product'] = code
            st['dyn'] = '%s|%s|%d|%s' % (kind, cat, qty, u)
            await e.edit('<b>КАК УДОБНЕЕ ОПЛАТИТЬ?</b>\n\n<b>%g</b> за «%s»' % (price, title),
                         buttons=[[Button.inline('звёздами', b'pay:stars'), Button.inline('криптой USDT', b'pay:crypto')],
                                  [Button.inline('назад в меню', b'menu')]])
            return
        if data.startswith('fa:') or data.startswith('fc:'):
            pr = data.split(':', 2)
            if pr[0] == 'fa':
                cat, u = pr[1], pr[2]
            else:
                u, cat = pr[1], pr[2]
            await e.answer('захожу и проверяю')
            jn = await join_chat(u)
            live, prem, rep = await quick_report(u, 300)
            con = db()
            con.execute("insert or ignore into chats (cat, link, added, status) values (?,?,?,'')", (cat, u, now_iso()))
            con.execute("update chats set status=? where cat=? and link=?", (('ок' if live else 'нет'), cat, u))
            con.commit()
            con.close()
            kb = []
            if live >= 10:
                q = min(live, 1000)
                kb.append([Button.inline('живые %d · %g' % (q, price_for('live', q)), ('dq:%s:%s:live:%d' % (cat, u, q)).encode())])
            if prem >= 5:
                kb.append([Button.inline('премиум %d · %g' % (prem, price_for('prem', prem)), ('dq:%s:%s:prem:%d' % (cat, u, prem)).encode())])
            kb.append([Button.inline('назад в меню', b'menu')])
            await e.edit('%s → <b>%s</b>\nвход: %s\n\n%s' % (u, cat, jn, rep), buttons=kb)
            return
        if data.startswith('fp:'):
            u = data[3:]
            cats = sorted(BASE_CATS)
            rows = [cats[k:k + 2] for k in range(0, len(cats), 2)]
            kb = [[Button.inline(c, ('fc:%s:%s' % (u, c)).encode()) for c in r] for r in rows]
            await e.edit('%s — в какую категорию?' % u, buttons=kb)
            return
        if data == 'ref':
            await e.edit(ref_text(uid), buttons=back_kb())
            return
        if data == 'wallet':
            await e.answer('USDT TRC20\n' + os.getenv('USDT_ADDR', ''), alert=True)
            return
        if data.startswith('o:'):
            c = product(data[2:])
            if c:
                st['product'] = c['code']
                save_lead(uid, interest=c['code'])
                cop = coupon(st.get('coupon'))
                price, off = price_with(c, cop)
                try:
                    await e.edit(bot_info(c, price), buttons=bot_info_kb(c['code'], price))
                except Exception as ex:
                    print('o: fail', type(ex).__name__, ex)
            return
        if data.startswith('dm:'):
            _, code, arg = data.split(':')
            try:
                await run_demo(client, e, uid, st, code, arg)
            except Exception as ex:
                print('demo', code, type(ex).__name__, ex)
            return
        if data == 'p:base0':
            await e.edit('<b>ПОДОБРАТЬ БАЗУ</b>\n\nвыбери вертикаль — покажу доступные чаты, качество и цену', buttons=cat_kb())
            return
        if data.startswith('p:'):
            c = product(data[2:])
            if not c:
                return
            st['product'] = c['code']
            save_lead(uid, interest=c['code'])
            cop = coupon(st.get('coupon'))
            price, off = price_with(c, cop)
            await e.edit(card(c, cop), buttons=card_kb(c['code'], price, c['code'] in DEMOS))
            return
        if data == 'buy':
            c = product(st.get('product', ''))
            if not c:
                await e.edit('выбери товар', buttons=menu_kb())
                return
            if c['delivery'] == 'base' and c['code'].startswith('base') and not st.get('chat'):
                st['await'] = 'chat'
                await e.edit('пришли ссылку или @ник чата, из которого собрать базу', buttons=back_kb())
                return
            price, off = price_with(c, coupon(st.get('coupon')))
            await e.edit('<b>КАК УДОБНЕЕ ОПЛАТИТЬ?</b>\n\n<b>%g</b> за «%s»%s' % (price, c['title'], ('\n\nподписка: каждый месяц, отменить можно в любой момент' if c['delivery'] == 'sub' else '')),
                         buttons=[[Button.inline('звёздами', b'pay:stars'), Button.inline('криптой USDT', b'pay:crypto')],
                                  [Button.inline('назад в меню', b'menu')]])
            return
        if data == 'pay:crypto':
            try:
                await invoice(uid)
            except Exception as ex:
                print('crypto fail', ex)
                await e.respond('крипта не ответила: %s' % type(ex).__name__)
            return
        if data == 'pay:stars':
            await invoice_stars(uid)
            return

    def new_order(uid, code, amount, cop, inv_id, note):
        con = db()
        cur = con.execute("insert into orders (client_id, product, qty, amount, coupon, invoice_id, status, created_at, note) values (?,?,?,?,?,?,?,?,?)",
                          (uid, code, 1, amount, (cop['code'] if cop else ''), inv_id, 'new', now_iso(), note))
        con.commit()
        oid = cur.lastrowid
        con.close()
        return oid

    async def invoice(uid):
        c = product(STATE[uid].get('product', ''))
        cop = coupon(STATE[uid].get('coupon'))
        amount, off = price_with(c, cop)
        inv = pay('createInvoice', asset='USDT', amount=('%g' % amount), description=c['title'], payload=str(uid))
        oid = new_order(uid, c['code'], amount, cop, str(inv['invoice_id']), (STATE[uid].get('dyn') or STATE[uid].get('chat', '')))
        print('zakaz', oid, 'USDT %g' % amount, 'ot', uid)
        await client.send_message(uid, 'счёт <b>%g</b> за «%s»\nоплатить: %s' % (amount, c['title'], inv['bot_invoice_url']), buttons=back_kb())

    async def invoice_stars(uid):
        c = product(STATE[uid].get('product', ''))
        cop = coupon(STATE[uid].get('coupon'))
        amount, off = price_with(c, cop)
        stars = max(1, int(round(amount * STARS)))
        oid = new_order(uid, c['code'], amount, cop, 'stars', (STATE[uid].get('dyn') or STATE[uid].get('chat', '')))
        params = {'chat_id': uid, 'title': c['title'], 'description': (c['descr'] or '')[:250],
                  'payload': str(oid), 'currency': 'XTR',
                  'prices': [{'label': c['title'], 'amount': stars}]}
        if c['delivery'] == 'sub':
            params['subscription_period'] = 2592000
        try:
            bot_api('sendInvoice', **params)
            print('zakaz', oid, 'STARS', stars, 'ot', uid)
        except Exception as ex:
            print('stars fail', ex)
            await client.send_message(uid, 'звёзды не прошли, давай криптой')
            await invoice(uid)

    async def paid_stars(uid, payload):
        try:
            oid = int(str(payload))
        except Exception:
            return
        con = db()
        r = con.execute("select client_id, amount, product, coupon from orders where id=?", (oid,)).fetchone()
        if not r:
            con.close()
            return
        until = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(timespec='seconds')
        if r['product'] == 'serv':
            con.execute("create table if not exists subs (uid integer primary key, until text, updated_at text)")
            con.execute("insert or replace into subs (uid, until, updated_at) values (?,?,?)", (r['client_id'], until, now_iso()))
        con.execute("update orders set status='paid', paid_at=? where id=?", (now_iso(), oid))
        if r['coupon']:
            con.execute("update coupons set used = used + 1 where code=?", (r['coupon'],))
        con.commit()
        con.close()
        print('OPLACHENO zvezdami', oid)
        p = str(r['product'])
        if p == 'serv':
            await client.send_message(r['client_id'], 'подписка активна до %s. дальше спишется автоматически.' % until[:10])
        elif p.startswith('dyn'):
            await client.send_message(r['client_id'], 'оплата получена. собираю базу, файлы пришлю сюда в течение пары минут.')
            asyncio.create_task(deliver_dyn(client, r['client_id']))
        elif p.startswith('base') or p == 'podpiska':
            await client.send_message(r['client_id'], 'оплата получена. собираю базу, пришлю файлы в течение пары минут.')
            asyncio.create_task(send_base(client, r['client_id'], (STATE.get(r['client_id']) or {}).get('chat', ''), PARSE_LIMIT, note='\\n\\n(оплаченный заказ)'))
        else:
            await client.send_message(r['client_id'], 'оплата получена. пришлю бота и команду установки в течение 1-3 часов.')
        if OWNER:
            await client.send_message(OWNER, 'ПРОДАЖА (stars) %g · %s · uid %s' % (float(r['amount']), p, r['client_id']))

    async def poller():
        while True:
            try:
                con = db()
                rows = con.execute("select id, invoice_id, client_id, amount, product, coupon from orders where status='new' and invoice_id is not null").fetchall()
                con.close()
                for r in rows:
                    res = pay('getInvoices', invoice_ids=str(r['invoice_id']))
                    items = res.get('items') if isinstance(res, dict) else res
                    if not items:
                        continue
                    if items[0].get('status') == 'paid':
                        con = db()
                        con.execute("update orders set status='paid', paid_at=? where id=?", (now_iso(), r['id']))
                        if r['coupon']:
                            con.execute("update coupons set used = used + 1 where code=?", (r['coupon'],))
                        con.commit()
                        con.close()
                        p = str(r['product'])
                        if p.startswith('base') or p == 'podpiska':
                            txt = 'оплата получена. собираю базу, пришлю файлы сюда в течение пары минут.'
                            asyncio.create_task(send_base(client, uid, (STATE.get(uid) or {}).get('chat', ''), PARSE_LIMIT, note='\n\n(оплаченный заказ)'))
                        elif p.startswith('dyn'):
                            txt = 'оплата получена. собираю базу, файлы пришлю сюда в течение пары минут.'
                            asyncio.create_task(deliver_dyn(client, uid))
                        elif p == 'rassylka':
                            txt = 'оплата получена. запускаю рассылку, отчёт пришлю в течение дня.'
                        else:
                            txt = 'оплата получена. пришлю бота и команду установки в течение 1-3 часов.'
                        await client.send_message(r['client_id'], txt)
                        if OWNER:
                            await client.send_message(OWNER, 'ПРОДАЖА %g · %s · uid %s' % (float(r['amount']), p, r['client_id']))
            except Exception as ex:
                print('poll', type(ex).__name__, ex)
            await asyncio.sleep(30)

    async def closer():
        await ref_reward_sweep(client)
        while True:
            try:
                con = db()
                cut = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(timespec='seconds')
                rows = con.execute("select uid, username, interest, demo from botleads where uid <> ? and orders=0 and coupon_sent=0 and (demo>0 or interest<>'') and last_seen < ? order by last_seen desc limit 8", (OWNER, cut)).fetchall()
                for r in rows:
                    code = ('L' + str(r['uid']))[-8:].upper()
                    until = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec='seconds')
                    con.execute("insert or replace into coupons (code, percent, amount_off, max_uses, used, active, until, promo) values (?,15,0,1,0,1,?,0)", (code, until))
                    con.execute("update botleads set coupon_sent=1 where uid=?", (r['uid'],))
                    con.commit()
                    what = (r['interest'] or '').split(',')
                    what = what[-1] if what and what[-1] else 'витрину'
                    txt = ('смотрел «%s», но так и не забрал\n\n'
                           'держи личный купон <code>%s</code> — минус 15%%, действует сутки и только для тебя\n\n'
                           'введи кнопкой «купон» или открой по ссылке') % (what, code)
                    try:
                        await client.send_message(r['uid'], txt, buttons=[[Button.url('открыть витрину', 'https://t.me/hunter_pay_bot')]])
                        print('closer ->', r['uid'], code)
                    except Exception as ex:
                        print('closer send fail', r['uid'], ex)
                    await asyncio.sleep(3)
                con.close()
            except Exception as ex:
                print('closer', type(ex).__name__, ex)
            await asyncio.sleep(300)

    @client.on(events.Raw(types=[tl_types.UpdateBotPrecheckoutQuery]))
    async def pre(e):
        try:
            bot_api('answerPreCheckoutQuery', pre_checkout_query_id=e.query_id, ok=True)
            print('precheckout ok')
        except Exception as ex:
            print('precheckout fail', ex)

    client.loop.create_task(poller())
    client.loop.create_task(closer())
    print("READY", flush=True)    # --- subsys hook ---
    try:
        import subsys as _subsys
        _subsys.install(globals(), locals())
    except Exception as _ex:
        print('subsys install fail:', _ex)
    await client.run_until_disconnected()

asyncio.run(main())
