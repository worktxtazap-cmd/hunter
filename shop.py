# shop.py - касса: витрина, купон, счёт в CryptoBot, заказ на выдачу
import asyncio, json, os, sqlite3, urllib.request
from datetime import datetime, timezone

from dotenv import load_dotenv
from telethon import TelegramClient, Button, events
from telethon.errors import FloodWaitError

load_dotenv('.env')
DB = os.getenv('HUNTER_DB', 'hunter.db')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
PAY_TOKEN = os.getenv('CRYPTOPAY_TOKEN', '')
OWNER = int(os.getenv('OWNER_ID', '0'))
SESSION = os.getenv('SHOP_SESSION', 'sessions/shop')

PAY_API = 'https://pay.crypt.bot/api/'

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def db():
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    return con

def pay(method, **params):
    req = urllib.request.Request(
        PAY_API + method,
        data=json.dumps(params).encode(),
        headers={'Crypto-Pay-API-Token': PAY_TOKEN, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    if not d.get('ok'):
        raise RuntimeError(str(d))
    return d['result']

def products():
    con = db()
    rows = con.execute("select * from products where active=1 order by price").fetchall()
    con.close()
    return rows

def product(code):
    con = db()
    r = con.execute("select * from products where code=?", (code,)).fetchone()
    con.close()
    return r

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

def card(c, cop=None):
    price, off = price_with(c, cop)
    lines = ['<b>%s</b>' % c['title'], '',
             '<code>%s</code>' % c['descr'].replace('. ', '\n'),
             '',
             '<b>$%s</b> за %s' % (('%g' % price), c['unit'])]
    if off:
        lines.append('<s>$%g</s>  минус $%g по купону %s' % (float(c['price']), off, cop['code']))
    lines += ['', 'срок 1-3 часа · оплата USDT или TON']
    return '\n'.join(lines)

STATE = {}

def menu_kb():
    rows = [[Button.inline('%s · $%g' % (c['title'], float(c['price'])), ('p:' + c['code']).encode())] for c in products()]
    rows.append([Button.inline('купон', b'coupon'), Button.inline('кошелёк', b'wallet')])
    return rows

def back_kb():
    return [[Button.inline('назад', b'menu')]]

async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    client.parse_mode = 'html'
    await client.start(bot_token=BOT_TOKEN)
    me = await client.get_me()
    print('касса запущена:', me.username)

    async def show_menu(uid, edit=None, note=''):
        txt = '<b>Касса</b>\nВыбирай, что нужно — счёт придёт сюда же.'
        if note:
            txt += '\n\n' + note
        if edit:
            await edit.edit(txt, buttons=menu_kb())
        else:
            await client.send_message(uid, txt, buttons=menu_kb())

    @client.on(events.NewMessage())
    async def msg(e):
        if not e.sender_id:
            return
        uid = e.sender_id
        txt = (e.raw_text or '').strip()
        st = STATE.setdefault(uid, {})

        if txt.startswith('/start'):
            parts = txt.split()
            if len(parts) > 1:
                cop = coupon(parts[1])
                st['coupon'] = cop['code'] if cop else ''
            note = ''
            if st.get('coupon'):
                c = coupon(st['coupon'])
                note = 'купон <code>%s</code> принят, минус %d%%' % (c['code'], c['percent'])
            await show_menu(uid, note=note)
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

        if st.get('await') == 'chat':
            st['await'] = ''
            link = txt.split()[0]
            try:
                await client.get_entity(link)
            except Exception:
                st['await'] = 'chat'
                await e.respond('не нашёл этот чат, проверь ссылку или ник')
                return
            st['chat'] = link
            await invoice(uid, link)
            return

        await e.respond('нажми /start')

    @client.on(events.CallbackQuery())
    async def cb(e):
        uid = e.sender_id
        st = STATE.setdefault(uid, {})
        data = (e.data or b'').decode()
        if data == 'menu':
            await show_menu(uid, edit=e)
            return
        if data == 'coupon':
            st['await'] = 'coupon'
            await e.edit('пришли код купона одним сообщением', buttons=back_kb())
            return
        if data == 'wallet':
            await e.answer('USDT TRC20\n' + os.getenv('USDT_ADDR', ''), alert=True)
            return
        if data.startswith('p:'):
            c = product(data[2:])
            if not c:
                return
            st['product'] = c['code']
            cop = coupon(st.get('coupon'))
            price, off = price_with(c, cop)
            await e.edit(card(c, cop), buttons=[[Button.inline('заказать · $%g' % price, b'buy'), Button.inline('назад', b'menu')]])
            return
        if data == 'buy':
            c = product(st.get('product', ''))
            if not c:
                await e.edit('выбери товар', buttons=menu_kb())
                return
            if c['delivery'] == 'base' and not st.get('chat'):
                st['await'] = 'chat'
                await e.edit('пришли ссылку или @ник чата, из которого собрать базу', buttons=back_kb())
                return
            await invoice(uid, st.get('chat', ''))

    async def invoice(uid, link):
        c = product(STATE[uid].get('product', ''))
        cop = coupon(STATE[uid].get('coupon'))
        amount, off = price_with(c, cop)
        inv = pay('createInvoice', asset='USDT', amount=('%g' % amount), description=c['title'], payload=str(uid))
        con = db()
        cur = con.execute("insert into orders (client_id, product, qty, amount, coupon, invoice_id, status, created_at, note) values (?,?,?,?,?,?,?,?,?)",
                          (uid, c['code'], 1, amount, (cop['code'] if cop else ''), str(inv['invoice_id']), 'new', now_iso(), link))
        con.commit()
        oid = cur.lastrowid
        con.close()
        print('заказ', oid, 'на $%g' % amount, 'от', uid)
        await client.send_message(uid, 'счёт <b>$%g</b> за «%s»\nоплатить: %s' % (amount, c['title'], inv['bot_invoice_url']), buttons=back_kb())

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
                        await client.send_message(r['client_id'], 'оплата получена. собираю базу, вернусь со ссылками в течение 1-3 часов.')
                        if OWNER:
                            await client.send_message(OWNER, 'ПРОДАЖА $%g · %s' % (float(r['amount']), r['product']))
            except Exception as ex:
                print('poll', type(ex).__name__, ex)
            await asyncio.sleep(30)

    client.loop.create_task(poller())
    await client.run_until_disconnected()

asyncio.run(main())
