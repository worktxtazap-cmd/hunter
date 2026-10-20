# build.py - выдача оплаченных заказов: собрать базу, превью, отдать ссылки
import json, os, re, sqlite3, subprocess, urllib.parse, urllib.request
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv('.env')

DB = os.getenv('HUNTER_DB', 'hunter.db')
TOKEN = os.getenv('BOT_TOKEN', '')
OWNER = os.getenv('OWNER_ID', '')
REPO = 'https://cdn.jsdelivr.net/gh/worktxtazap-cmd/hunter@main/'
PY = '.venv/bin/python'

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def tg(method, **params):
    url = 'https://api.telegram.org/bot%s/%s' % (TOKEN, method)
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def clean(s):
    s = (s or '').strip()
    s = re.sub(r'^https?://t\.me/', '', s)
    s = re.sub(r'^https?://telegram\.me/', '', s)
    return s.lstrip('@').split('/')[0].split('?')[0]

def main():
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "select o.*, p.delivery, p.title from orders o join products p on p.code = o.product "
        "where o.status = 'paid' and p.delivery = 'base'").fetchall()
    if not rows:
        print('оплаченных заказов нет')
        return
    for o in rows:
        chat = clean(o['note'])
        print('собираю', chat, 'для', o['client_id'])
        r = subprocess.run([PY, 'demo.py', chat, '1000'], capture_output=True, text=True)
        print((r.stdout or r.stderr).strip()[-400:])
        src = 'demo_%s.csv' % chat
        if not os.path.exists(src):
            tg('sendMessage', chat_id=o['client_id'],
               text='не смог собрать базу по %s. проверю руками и вернусь.' % chat)
            if OWNER:
                tg('sendMessage', chat_id=OWNER, text='заказ %s: сборка не удалась, чат %s' % (o['id'], chat))
            continue
        out_csv = 'base_%s.csv' % chat
        out_html = 'base_%s.html' % chat
        os.replace(src, out_csv)
        subprocess.run([PY, 'mkpreview.py', out_csv, out_html], capture_output=True, text=True)
        subprocess.run(['git', 'add', out_csv, out_html])
        subprocess.run(['git', 'commit', '-m', 'база %s' % chat], capture_output=True, text=True)
        subprocess.run(['git', 'push'], capture_output=True, text=True)
        with open(out_csv, encoding='utf-8-sig') as f:
            n = sum(1 for _ in f) - 1
        tg('sendMessage', chat_id=o['client_id'],
           text='база готова, контактов: %d\nпревью: %s%s\nфайл: %s%s' % (n, REPO, out_html, REPO, out_csv))
        con.execute("update orders set status='delivered', delivered_at=? where id=?", (now_iso(), o['id']))
        con.commit()
        if OWNER:
            tg('sendMessage', chat_id=OWNER, text='выдал заказ %s · %s · %d контактов' % (o['id'], chat, n))
    con.close()

main()
