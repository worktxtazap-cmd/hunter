# -*- coding: utf-8 -*-
# subsys.py v2 - HUNTER: поиск чатов, парсинг, цены, выдача
import os, re, csv, json, time, asyncio, sqlite3
import urllib.request, urllib.parse

from telethon import events, functions
from telethon.tl import types
from telethon.errors import FloodWaitError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'hunter.db')
BASES_DIR = os.path.join(BASE_DIR, 'bases')

G = {}
SG = {}
CFG = {}
FOUND = {}
SUBS = ('fqmenu', 'fq', 'fc', 'fp', 'fx')
CMDS = ('/find', '/fqmenu', '/selftest', '/probe', '/build', '/pool', '/join', '/add', '/del')


def log(*a):
    try:
        print('[subsys]', *a, flush=True)
    except Exception:
        pass


def _load_env():
    p = os.path.join(BASE_DIR, '.env')
    if not os.path.exists(p):
        return
    try:
        for ln in open(p, encoding='utf-8', errors='ignore'):
            ln = ln.strip()
            if not ln or ln.startswith('#') or '=' not in ln:
                continue
            k, v = ln.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception as ex:
        log('env', ex)


def _e(k, d=''):
    v = os.getenv(k)
    return d if v in (None, '') else v


def _f(k, d):
    try:
        return float(_e(k, str(d)))
    except Exception:
        return float(d)


def _db():
    fn = G.get('db')
    if fn is not None:
        try:
            return fn()
        except Exception:
            pass
    return sqlite3.connect(DB_PATH)


def _tables():
    try:
        c = _db()
        cur = c.cursor()
        cols = []
        try:
            cols = [r[1] for r in cur.execute("pragma table_info(chats)").fetchall()]
        except Exception:
            cols = []
        if cols and 'added' not in cols:
            cur.execute("drop table chats")
            log('chats peresozdana: %s' % ','.join(cols))
        cur.execute("create table if not exists chats (cat text, link text, added text, status text, primary key (cat, link))")
        cur.execute("create table if not exists parsed(link text primary key, ts integer, n integer)")
        c.commit()
        c.close()
    except Exception as ex:
        log('tables', ex)


CATS = {
    'крипта': ['crypto', 'bitcoin', 'trading', 'defi'],
    'фриланс': ['freelance', 'фриланс', 'дизайн', 'копирайтинг'],
    'hr': ['вакансии', 'работа', 'hr', 'jobs'],
    'smm': ['smm', 'маркетинг', 'реклама'],
    'маркетплейсы': ['маркетплейс', 'wildberries', 'ozon', 'селлер'],
    'инфобиз': ['инфобиз', 'эксперты', 'курсы'],
    'дейтинг': ['dating', 'знакомства', 'дейтинг'],
    'ставки': ['ставки', 'беттинг', 'спорт'],
}

SEED = {
    'crypto': ['cryptocurrencytalk', 'crypto', 'bitcoin'],
    'freelance': ['freelancechat', 'freelancers'],
    'hr': ['vacancychat', 'rabota'],
    'smm': ['smmchat'],
    'market': ['marketplacechat'],
    'infobiz': ['infobizchat'],
    'dating': ['datingchat'],
    'gamble': ['bettingchat'],
}


def _seed():
    try:
        c = _db()
        cur = c.cursor()
        t = time.strftime('%Y-%m-%dT%H:%M:%S')
        for cat, links in SEED.items():
            for lk in links:
                cur.execute("insert or ignore into chats(cat, link, added, status) values(?,?,?,'')", (cat, lk, t))
        c.commit()
        c.close()
    except Exception as ex:
        log('seed', ex)


def seed_chats():
    _seed()


def cat_links(cat):
    return list(SEED.get(cat, []))


def err_ru(ex):
    s = ex.__class__.__name__
    if 'FloodWait' in s:
        return 'лимит, ждать %s сек' % getattr(ex, 'seconds', '?')
    if 'ChatAdminRequired' in s:
        return 'нет доступа к списку участников'
    if 'ChannelPrivate' in s:
        return 'закрытый чат'
    if 'UsernameNotOccupied' in s:
        return 'нет такого юзернейма'
    if 'UsernameInvalid' in s:
        return 'кривая ссылка'
    if 'InviteHashExpired' in s:
        return 'приглашение протухло'
    if 'TooManyRequests' in s:
        return 'слишком часто'
    return (s + ': ' + str(ex))[:90]


def btn_label(a, b=None):
    if isinstance(b, int):
        s = str(a)
        n = b
    else:
        s = ('%s — %s' % (a, b)) if b else str(a)
        n = 60
    s = re.sub(r'[\\r\\n\\t]+', ' ', s).strip()
    s = ''.join(ch for ch in s if ord(ch) >= 32)
    return s[:n] or '—'


def person_ok(u):
    try:
        if getattr(u, 'bot', False) or getattr(u, 'deleted', False):
            return False
        return bool(getattr(u, 'first_name', None) or getattr(u, 'last_name', None) or getattr(u, 'username', None))
    except Exception:
        return False


def nick_ok(u):
    try:
        if not person_ok(u):
            return False
        if getattr(u, 'scam', False) or getattr(u, 'fake', False):
            return False
        un = getattr(u, 'username', None)
        if not un or len(un) < 4:
            return False
        return re.match(r'^[A-Za-z0-9_]+$', un) is not None
    except Exception:
        return False


def _parser():
    u = G.get('USER')
    if u is not None:
        return u
    try:
        from telethon import TelegramClient
        cands = [_e('USERSESSION'), 'sessions/shopuser', _e('SENDER_SESSION'), _e('SESSION_NAME')]
        sess = None
        for c in cands:
            if not c:
                continue
            p = c if os.path.isabs(c) else os.path.join(BASE_DIR, c)
            if os.path.exists(p + '.session'):
                sess = p
                break
        if sess is None:
            sess = os.path.join(BASE_DIR, 'sessions', 'shopuser')
        api = int(_e('API_ID', '0') or '0')
        h = _e('API_HASH')
        if api and h:
            u = TelegramClient(sess, api, h)
            G['USER'] = u
            log('parser session:', sess)
            return u
    except Exception as ex:
        log('parser init', ex)
    return None


async def join_ent(ent):
    u = _parser()
    if u is None:
        return
    try:
        await u(functions.channels.JoinChannelRequest(ent))
    except Exception as ex:
        if 'AlreadyParticipant' not in ex.__class__.__name__:
            log('join', err_ru(ex))


async def leave_ent(ent):
    u = _parser()
    if u is None:
        return
    try:
        await u(functions.channels.LeaveChannelRequest(ent))
    except Exception as ex:
        log('leave', err_ru(ex))


async def _grab(ent, limit=800):
    u = _parser()
    out = []
    if u is None:
        return out
    async for p in u.iter_participants(ent, aggressive=True):
        if person_ok(p):
            out.append(p)
        if len(out) >= limit:
            break
    return out


async def parse_chat(ent, limit=800):
    joined = False
    try:
        await join_ent(ent)
        joined = True
        await asyncio.sleep(3)
        return await _grab(ent, limit)
    except FloodWaitError as ex:
        await asyncio.sleep(min(ex.seconds, 30))
        try:
            return await _grab(ent, limit)
        except Exception:
            return []
    except Exception as ex:
        log('parse', err_ru(ex))
        return []
    finally:
        if CFG.get('PARSER_LEAVE') and joined:
            try:
                await asyncio.sleep(1)
                await leave_ent(ent)
            except Exception:
                pass


async def probe_parse(link):
    u = _parser()
    if u is None:
        return False, 'нет парсер-сессии'
    joined = False
    try:
        ent = await u.get_entity(link)
    except Exception as ex:
        log('probe %s: get_entity %s' % (link, err_ru(ex)))
        return False, err_ru(ex)
    is_chan = bool(getattr(ent, 'broadcast', False)) and not bool(getattr(ent, 'megagroup', False))
    log('probe %s: type=%s mega=%s bcast=%s' % (link, type(ent).__name__, getattr(ent, 'megagroup', None), getattr(ent, 'broadcast', None)))
    try:
        try:
            await join_ent(ent)
            joined = True
        except Exception as ex:
            log('probe %s: join %s' % (link, err_ru(ex)))
        await asyncio.sleep(2)
        n, err = 0, ('канал — список только у админов' if is_chan else 'участники скрыты')
        for agg in (False, True):
            try:
                got = await u.get_participants(ent, limit=60, aggressive=agg)
                n = len(got)
                log('probe %s: parts agg=%s n=%d' % (link, agg, n))
                if n:
                    break
            except Exception as ex:
                err = err_ru(ex)
                log('probe %s: parts agg=%s %s' % (link, agg, type(ex).__name__))
        if n == 0:
            return False, err
        return True, 'видно %d' % n
    finally:
        if CFG.get('PARSER_LEAVE') and joined:
            try:
                await leave_ent(ent)
            except Exception:
                pass


probe_chat = probe_parse


async def find_chats(word, limit=25):
    u = _parser()
    if u is None:
        return []
    out, seen = [], set()
    for kind in ('contacts', 'global'):
        try:
            if kind == 'contacts':
                r = await u(functions.contacts.SearchRequest(q=word, limit=limit))
            else:
                r = await u(functions.messages.SearchGlobalRequest(q=word, filter=types.InputMessagesFilterEmpty(), min_date=None, max_date=None, offset_rate=0, offset_peer=types.InputPeerEmpty(), offset_id=0, limit=limit))
        except FloodWaitError as ex:
            await asyncio.sleep(min(ex.seconds, 20))
            continue
        except Exception as ex:
            log('search ' + kind, err_ru(ex))
            continue
        for c in list(getattr(r, 'chats', []) or []):
            cid = getattr(c, 'id', None)
            if cid is None or cid in seen:
                continue
            seen.add(cid)
            out.append(c)
    return out


async def pick_parseable(ents, want=6):
    ok = []
    for ent in ents:
        good, _ = await probe_parse(ent)
        if good:
            ok.append(ent)
        if len(ok) >= want:
            break
    return ok


def _fmt(p):
    p = float(p)
    if p >= 1:
        return ('%.2f' % p).rstrip('0').rstrip('.')
    return ('%.4f' % p).rstrip('0').rstrip('.')


def price_for(kind, n):
    if CFG.get('TESTMODE'):
        return CFG.get('TEST_PRICE', 0.001)
    rate = CFG['RATE_PREMIUM'] if kind == 'prem' else CFG['RATE_LIVE']
    p = rate * float(n) / 1000.0
    return round(max(p, CFG.get('MIN_PRICE', 3.0)), 2)


def cat_kb():
    rows, row = [], []
    for c in CATS:
        row.append((btn_label(c, 18), 'fq:' + c))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([('другое слово', 'fx:any')])
    return rows


def _guess_cat(word):
    for c, keys in CATS.items():
        if word == c or word in keys:
            return c
    return word[:20] or 'микс'


def _passport(cat, kind, cnt, prem, src, path):
    t = ['ПАСПОРТ БАЗЫ', 'вертикаль: ' + cat,
         'тир: ' + ('премиум' if kind == 'prem' else 'живые обычные'),
         'контактов: %d' % cnt, 'из них премиум: %d' % prem, 'источник: ' + src,
         'собрано: ' + time.strftime('%Y-%m-%d %H:%M'), '',
         'формат: CSV, utf-8 с BOM, разделитель ;', 'колонки: nick;name;tg_id;premium',
         'отсев: боты, удалённые, скам, без @ника, дубли']
    open(path, 'w', encoding='utf-8').write('\n'.join(t))


async def find_send(e, word):
    uid = e.sender_id
    word = (word or '').strip().lower()
    cat = _guess_cat(word)
    m = await e.reply('ищу «%s», пару секунд…' % word)
    if _parser() is None:
        try:
            await m.edit('парсер не подключён (нет сессии).')
        except Exception:
            pass
        return
    ents = await find_chats(word, 25)
    if not ents:
        try:
            await m.edit('по «%s» ничего. дай другое слово.' % word)
        except Exception:
            pass
        return
    ok = await pick_parseable(ents[:12], 6)
    if not ok:
        try:
            await m.edit('нашёл %d чатов, но ни один не парсится (участники скрыты).' % len(ents))
        except Exception:
            pass
        return
    FOUND[uid] = {'cat': cat, 'word': word, 'ents': ok}
    rows = []
    for i, ent in enumerate(ok):
        t = getattr(ent, 'title', None) or getattr(ent, 'username', '') or str(getattr(ent, 'id', i))
        rows.append([(btn_label(t, 34), 'fc:%d' % i)])
    rows.append([('другое слово', 'fx:any')])
    try:
        await m.edit('нашёл %d годных чатов по «%s». выбери, откуда брать:' % (len(ok), word), buttons=rows)
    except Exception as ex:
        log('edit', ex)


async def pick_chat(e, uid, idx):
    st = FOUND.get(uid)
    if not st or idx >= len(st['ents']):
        return await e.edit('поиск потерялся, жми /find заново')
    ent = st['ents'][idx]
    title = getattr(ent, 'title', None) or getattr(ent, 'username', '')
    try:
        await e.edit('беру «%s», вхожу и парсю…' % btn_label(title, 30))
    except Exception:
        pass
    us = await parse_chat(ent, 800)
    if not us:
        return await e.edit('в «%s» пусто или закрыто. жми /find' % btn_label(title, 30))
    seen, live = set(), []
    for u in us:
        if u.id in seen:
            continue
        seen.add(u.id); live.append(u)
    if not live:
        return await e.edit('живых без ботов — ноль. жми /find')
    prem = [u for u in live if getattr(u, 'premium', False)]
    fn = os.path.join(BASES_DIR, 'base_%s_%d.csv' % (re.sub(r'\W+', '', st['cat']), int(time.time())))
    with open(fn, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['nick', 'name', 'tg_id', 'premium'])
        for u in live:
            w.writerow(['@' + (u.username or ''),
                        ((u.first_name or '') + ' ' + (u.last_name or '')).strip(), u.id,
                        'да' if getattr(u, 'premium', False) else ''])
    st['live'] = len(live); st['prem'] = len(prem); st['csv'] = fn; st['title'] = title
    pl = price_for('live', len(live))
    rows = [[('обычная %s' % _fmt(pl), 'fp:live')]]
    if prem:
        rows[0].append(('премиум %s' % _fmt(price_for('prem', len(prem))), 'fp:prem'))
    txt = ('чат: %s\nсобрано живых: %d\nс @ником: %d\nс премиумом: %d\n\n'
           'обычная база: %d контактов — %s\nпремиум-база: %d контактов' % (
               btn_label(title, 30), len(live), len(live), len(prem), len(live), _fmt(pl), len(prem)))
    try:
        await e.edit(txt, buttons=rows)
    except Exception as ex:
        log('report', ex)


async def make_order(e, uid, kind):
    st = FOUND.get(uid)
    if not st or not st.get('csv'):
        return await e.edit('нет данных, жми /find заново')
    cnt = st['prem'] if kind == 'prem' else st['live']
    if not cnt:
        return await e.edit('в этой базе нет премиум-контактов')
    price = price_for(kind, cnt)
    code = 'dyn_%d_%s_%d' % (uid, kind, int(time.time()))
    txt_path = os.path.join(BASES_DIR, code + '.txt')
    _passport(st['cat'], kind, cnt, st['prem'], btn_label(st.get('title', ''), 40), txt_path)
    try:
        c = _db(); cur = c.cursor()
        cur.execute('insert or replace into dyn(code, uid, kind, cnt, cat, csv, txt, paid, ts) values(?,?,?,?,?,?,?,0,?)',
                    (code, uid, kind, cnt, st['cat'], st['csv'], txt_path, int(time.time())))
        c.commit(); c.close()
    except Exception as ex:
        log('order', ex)
    txt = 'база готова: %d контактов, %s\nцена: %s' % (cnt, st['cat'], _fmt(price))
    stars = max(1, int(round(price * CFG['STARS_PER_USD'])))
    if CFG.get('BOT_TOKEN'):
        link = _api('createInvoiceLink', {
            'title': 'База ' + st['cat'],
            'description': '%d контактов, %s' % (cnt, 'премиум' if kind == 'prem' else 'живые'),
            'payload': code, 'currency': 'XTR',
            'prices': json.dumps([{'label': 'База ' + st['cat'], 'amount': stars}])})
        if link:
            txt += '\n\nзвёздами (%d) → %s' % (stars, link)
    if CFG.get('CRYPTOPAY_TOKEN'):
        inv = _cryptopay('createInvoice', {'asset': 'USDT', 'amount': _fmt(price),
                                           'description': 'База ' + st['cat'],
                                           'payload': code, 'expires_in': 3600})
        if not inv:
            inv = _cryptopay('createInvoice', {'asset': 'USDT', 'amount': _fmt(max(price, 0.01)),
                                               'description': 'База ' + st['cat'],
                                               'payload': code, 'expires_in': 3600})
        if inv:
            txt += '\n\nкриптой %s USDT → %s' % (inv.get('amount', _fmt(price)), inv.get('bot_invoice_url'))
            try:
                asyncio.ensure_future(_poll_crypto(code, inv.get('invoice_id')))
            except Exception:
                pass
    addr = CFG.get('CRYPTO_ADDR')
    if addr:
        txt += '\n\nреквизит: %s USDT → %s' % (_fmt(price), addr)
    txt += '\n\nпосле оплаты жми кнопку — выдам файл и паспорт.'
    try:
        await e.edit(txt, buttons=[[('я оплатил', 'fx:pay:' + code)]])
    except Exception as ex:
        log('pay', ex)


async def deliver(e, code, uid=None):
    cl = G.get('client')
    try:
        c = _db(); cur = c.cursor()
        cur.execute('select uid, kind, cnt, cat, csv, txt, paid from dyn where code=?', (code,))
        r = cur.fetchone()
    except Exception as ex:
        log('deliver', ex)
        return
    if not r:
        if e:
            await e.respond('заказ %s не найден' % code)
        return
    if r[6]:
        if e:
            await e.respond('этот заказ уже выдан')
        return
    uid = uid or r[0]
    if not os.path.exists(r[4]):
        if e:
            await e.respond('файл базы потерялся, жми /find заново')
        return
    try:
        await cl.send_file(uid, r[4], caption='Твоя база: %s, %d контактов, %s' % (r[3], r[2], r[1]))
        if os.path.exists(r[5]):
            await cl.send_file(uid, r[5], caption='Паспорт базы')
    except Exception as ex:
        log('send', ex)
    try:
        cur.execute('update dyn set paid=1 where code=?', (code,))
        c.commit(); c.close()
    except Exception:
        pass
    if CFG.get('ADMIN'):
        try:
            await cl.send_message(int(CFG['ADMIN']), 'Оплата: %s | %s | %d | %s' % (code, r[1], r[2], r[3]))
        except Exception:
            pass
    rr = SG.get('ref_reward_sweep')
    if rr:
        try:
            await rr(cl)
        except Exception as ex:
            log('ref', ex)


def _api(method, params):
    tok = CFG.get('BOT_TOKEN')
    if not tok:
        return None
    try:
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request('https://api.telegram.org/bot%s/%s' % (tok, method), data=data)
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode())
        return j.get('result') if j.get('ok') else None
    except Exception as ex:
        log('api ' + method, ex)
        return None


def _cryptopay(method, params):
    tok = CFG.get('CRYPTOPAY_TOKEN')
    if not tok:
        return None
    try:
        data = json.dumps(params).encode()
        req = urllib.request.Request('https://pay.crypt.bot/api/' + method, data=data,
                                     headers={'Crypto-Pay-API-Token': tok, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode())
        if not j.get('ok'):
            log('cryptopay ' + method, j.get('error'))
            return None
        return j.get('result')
    except Exception as ex:
        log('cryptopay ' + method, ex)
        return None


async def _poll_crypto(code, inv_id):
    if not inv_id:
        return
    for _ in range(180):
        await asyncio.sleep(10)
        r = _cryptopay('getInvoices', {'invoice_ids': str(inv_id)})
        try:
            items = (r or {}).get('items') or []
            if items and items[0].get('status') == 'paid':
                await deliver(None, code)
                return
        except Exception:
            pass


async def selftest(e):
    out = []
    out.append('bot client: ' + ('ok' if G.get('client') else 'НЕТ'))
    u = _parser()
    out.append('парсер-сессия: ' + ('ok' if u else 'НЕТ'))
    if u:
        try:
            me = await u.get_me()
            out.append('парсер вошёл как: @%s (%s)' % (getattr(me, 'username', '?'), getattr(me, 'id', '?')))
        except Exception as ex:
            out.append('парсер get_me: ' + err_ru(ex))
    out.append('testmode: %s цена=%s' % (CFG.get('TESTMODE'), CFG.get('TEST_PRICE')))
    out.append('ставки live/prem/min: %s/%s/%s' % (CFG.get('RATE_LIVE'), CFG.get('RATE_PREMIUM'), CFG.get('MIN_PRICE')))
    out.append('звёзд за доллар: %s' % CFG.get('STARS_PER_USD'))
    out.append('bot token: ' + ('ok' if CFG.get('BOT_TOKEN') else 'НЕТ'))
    out.append('cryptopay: ' + ('ok' if CFG.get('CRYPTOPAY_TOKEN') else 'НЕТ'))
    out.append('админ: %s' % CFG.get('ADMIN'))
    ents = await find_chats('крипта', 10)
    out.append('search: %d' % len(ents))
    if ents:
        good, why = await probe_parse(ents[0])
        out.append('probe: %s %s' % (good, why))
    await e.reply(chr(10).join(out))


async def probe_cmd(e, arg):
    if not arg:
        return await e.reply('напиши: /probe ссылка')
    good, why = await probe_parse(arg)
    await e.reply('%s → %s' % (arg, why))


async def build_cmd(e, arg):
    cat = (arg or '').strip().lower()
    if cat not in CATS:
        return await e.reply('вертикали: ' + ', '.join(CATS))
    m = await e.reply('собираю «%s», это пара минут…' % cat)
    ents = await find_chats(cat, 30)
    ok = await pick_parseable(ents[:10], 4)
    allu, seen = [], set()
    for ent in ok:
        for u in await parse_chat(ent, 800):
            if u.id in seen:
                continue
            seen.add(u.id)
            allu.append(u)
    live = [u for u in allu if nick_ok(u)]
    fn = os.path.join(BASES_DIR, 'cat_%s_%d.csv' % (re.sub(r'\W+', '', cat), int(time.time())))
    with open(fn, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['nick', 'name', 'tg_id', 'premium'])
        for u in live:
            w.writerow(['@' + (u.username or ''), ((u.first_name or '') + ' ' + (u.last_name or '')).strip(), u.id, 'да' if getattr(u, 'premium', False) else ''])
    try:
        await m.edit('готово: %d контактов, источников %d' % (len(live), len(ok)))
    except Exception:
        pass
    await e.reply(file=fn)


async def pool_text():
    sdir = os.path.join(BASE_DIR, 'sessions')
    try:
        files = [f for f in os.listdir(sdir) if f.endswith('.session')]
    except Exception:
        files = []
    return 'сессий: %d' % len(files) + chr(10) + chr(10).join(files) + chr(10) + 'парсер: ' + ('ok' if _parser() else 'НЕТ')


async def join_cmd(e, arg):
    u = _parser()
    if not arg or u is None:
        return await e.reply('напиши: /join ссылка')
    try:
        ent = await u.get_entity(arg)
        await join_ent(ent)
        await e.reply('зашёл в %s' % btn_label(getattr(ent, 'title', arg), 30))
    except Exception as ex:
        await e.reply(err_ru(ex))


async def add_cmd(e, arg):
    parts = (arg or '').split()
    if len(parts) < 2:
        return await e.reply('напиши: /add крипта ссылка')
    try:
        c = _db()
        cur = c.cursor()
        cur.execute('insert or ignore into chats(cat, link, title, ts) values(?,?,?,?)', (parts[0], parts[1], parts[1], int(time.time())))
        c.commit()
        c.close()
        await e.reply('добавил %s в %s' % (parts[1], parts[0]))
    except Exception as ex:
        await e.reply(str(ex))


async def del_cmd(e, arg):
    if not arg:
        return await e.reply('напиши: /del ссылка')
    try:
        c = _db()
        cur = c.cursor()
        cur.execute('delete from chats where link=?', (arg,))
        c.commit()
        c.close()
        await e.reply('убрал ' + arg)
    except Exception as ex:
        await e.reply(str(ex))


async def msg_route(e, txt):
    parts = txt.split()
    cmd = parts[0].split('@')[0].lower()
    arg = ' '.join(parts[1:]).strip()
    if cmd in ('/find', '/fqmenu'):
        if arg:
            return await find_send(e, arg)
        return await e.reply('выбери вертикаль:', buttons=cat_kb())
    if cmd == '/selftest':
        return await selftest(e)
    if cmd == '/probe':
        return await probe_cmd(e, arg)
    if cmd == '/build':
        return await build_cmd(e, arg)
    if cmd == '/pool':
        return await e.reply(await pool_text())
    if cmd == '/join':
        return await join_cmd(e, arg)
    if cmd == '/add':
        return await add_cmd(e, arg)
    if cmd == '/del':
        return await del_cmd(e, arg)
    return None


async def cb_route(e, d):
    uid = e.sender_id
    pp = d.split(':')
    try:
        await e.answer()
    except Exception:
        pass
    if pp[0] == 'fqmenu':
        return await e.respond('выбери вертикаль:', buttons=cat_kb())
    if pp[0] == 'fq':
        return await find_send(e, pp[1])
    if pp[0] == 'fc':
        return await pick_chat(e, uid, int(pp[1]))
    if pp[0] == 'fp':
        return await make_order(e, uid, pp[1])
    if pp[0] == 'fx':
        if pp[1] == 'any':
            return await e.respond('напиши слово: /find крипта')
        if pp[1] == 'pay':
            return await deliver(e, pp[2], uid)
    return None


def _export(g):
    if g is None:
        return
    for n in ('probe_parse', 'btn_label', 'price_for'):
        f = globals().get(n)
        if f is not None:
            g[n] = f
            log('экспорт ' + n)


def deliver_dyn(*a, **kw):
    code = None
    for x in a:
        if isinstance(x, str) and x.startswith('dyn_'):
            code = x
    code = code or kw.get('code')
    if code:
        try:
            return asyncio.ensure_future(deliver(None, code, kw.get('uid')))
        except Exception:
            return None
    return None


def _hook():
    cl = G.get('client')
    if cl is None:
        log('hook: нет client')
        return
    for b, f in list(cl.list_event_handlers()):
        if getattr(f, '_sub', False):
            try:
                cl.remove_event_handler(f, b)
            except Exception:
                pass
    log('обработчиков в реестре: %d' % len(cl.list_event_handlers()))

    @cl.on(events.NewMessage())
    async def _sub_msg(e):
        try:
            t = (e.raw_text or '').strip()
        except Exception:
            t = ''
        if t.startswith('/') and t.split()[0].split('@')[0].lower() in ('/selftest', '/pool'):
            return await msg_route(e, t)
        return None
    _sub_msg._sub = True
    log('подсистема: /selftest и /pool, остальное отдано shop.py')


def install(g, loc=None):
    _load_env()
    G.update(g)
    SG.clear()
    SG.update(g)
    if loc:
        for kk in ('client', 'USER', 'db'):
            if kk in loc:
                G[kk] = loc[kk]
    CFG['RATE_LIVE'] = _f('RATE_LIVE', 4.0)
    CFG['RATE_PREMIUM'] = _f('RATE_PREMIUM', 8.0)
    CFG['MIN_PRICE'] = _f('MIN_PRICE', 3.0)
    CFG['TEST_PRICE'] = _f('TEST_PRICE', 0.001)
    CFG['TESTMODE'] = _e('TESTMODE', '0') == '1'
    CFG['PARSER_LEAVE'] = _e('PARSER_LEAVE', '1') == '1'
    CFG['STARS_PER_USD'] = _f('STARS_PER_USD', 50.0)
    CFG['BOT_TOKEN'] = _e('BOT_TOKEN') or _e('TOKEN')
    CFG['CRYPTOPAY_TOKEN'] = _e('CRYPTOPAY_TOKEN')
    CFG['CRYPTO_ADDR'] = _e('CRYPTO_ADDR')
    CFG['ADMIN'] = _e('OWNER') or _e('OWNER_ID')
    try:
        os.makedirs(BASES_DIR, exist_ok=True)
    except Exception:
        pass
    _tables()
    _seed()
    _export(g)
    _hook()
    log('installed testmode=%s live=%s prem=%s leave=%s' % (CFG['TESTMODE'], CFG['RATE_LIVE'], CFG['RATE_PREMIUM'], CFG['PARSER_LEAVE']))
