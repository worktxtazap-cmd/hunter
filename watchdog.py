# watchdog.py - сторож: службы, таймеры, живость, диск, бэкап базы, алерт в Избранное
import asyncio, os, sqlite3, subprocess, sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from telethon import TelegramClient

import guard

load_dotenv('.env')
DB = os.getenv('HUNTER_DB', 'hunter.db')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION = os.getenv('WATCH_SESSION', 'sessions/watch')
PEER = os.getenv('ALERT_PEER', 'me')

SERVICES = ['hunter.service', 'hunter-recv.service', 'hunter-shop.service']
TIMERS = ['hunter-sync.timer', 'hunter-watch.timer', 'hunter-drafts.timer', 'hunter-build.timer']
LOGS = ['logs/sync1.log', 'logs/sync2.log']
BACKUP_DIR = 'backups'
KEEP_DAYS = 7
DISK_MIN_MB = 500
SILENT_MIN = 40

def sh(*a):
    try:
        return subprocess.run(a, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception as e:
        return 'ERR ' + str(e)

def disk_mb():
    st = os.statvfs('.')
    return st.f_bavail * st.f_frsize // (1024 * 1024)

def backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dst = os.path.join(BACKUP_DIR, 'hunter-%s.db' % datetime.now().strftime('%Y-%m-%d'))
    if os.path.exists(dst):
        return None
    src = sqlite3.connect(DB)
    out = sqlite3.connect(dst)
    with out:
        src.backup(out)
    out.close(); src.close()
    for f in sorted(x for x in os.listdir(BACKUP_DIR) if x.endswith('.db'))[:-KEEP_DAYS]:
        os.remove(os.path.join(BACKUP_DIR, f))
    return 'бэкап базы: %s, %d КБ' % (os.path.basename(dst), os.path.getsize(dst) // 1024)

def check():
    p = []
    for s in SERVICES:
        st = sh('systemctl', 'is-active', s)
        if st != 'active':
            p.append('служба %s: %s' % (s, st))
    for t in TIMERS:
        st = sh('systemctl', 'is-active', t)
        if st != 'active':
            p.append('таймер %s: %s' % (t, st))
    if guard.in_window():
        for lg in LOGS:
            if not os.path.exists(lg):
                continue
            silent = int((datetime.now().timestamp() - os.path.getmtime(lg)) / 60)
            if silent > SILENT_MIN:
                p.append('%s молчит %d мин' % (lg, silent))
    free = disk_mb()
    if free < DISK_MIN_MB:
        p.append('мало места: %d МБ' % free)
    con = sqlite3.connect(DB, timeout=20)
    if con.execute('pragma quick_check').fetchone()[0] != 'ok':
        p.append('база битая')
    now_utc = datetime.now(timezone.utc)
    for name, cd in con.execute("select name, cooldown_until from accounts"):
        if cd:
            left = (datetime.fromisoformat(cd) - now_utc).total_seconds()
            if left > 24 * 3600:
                p.append('%s в кулдауне ещё %d ч' % (name, left // 3600))
    d = con.execute("select count(*) from hits where status='draft'").fetchone()[0]
    s = con.execute("select count(*) from hits where sent_at is not null").fetchone()[0]
    g = con.execute("select count(*) from hits where status='new' and username is not null and is_ad=0 and is_seller=0 and is_hr=0 and is_closed=0 and score>=7").fetchone()[0]
    if g < 10:
        p.append('мало целей: годных всего %d' % g)
    con.close()
    return p, d, s, g

async def send(text):
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.connect()
    if not await c.is_user_authorized():
        print('watch: NOT AUTHORIZED', SESSION)
        return
    m = await c.send_message(PEER, text)
    print('алерт отправлен, id', m.id, m.date)
    await c.disconnect()

def main():
    b = backup()
    if b:
        print(b)
    probs, drafts, sent, good = check()
    ts = datetime.now().strftime('%d.%m %H:%M')
    for x in probs:
        print(ts, 'ПРОБЛЕМА:', x)
    print('%s заготовок %d, отправлено всего %d, годных %d, место %d МБ' % (ts, drafts, sent, good, disk_mb()))
    if probs or '--test' in sys.argv:
        txt = 'HUNTER сторож ' + ts + '\n' + ('\n'.join(probs) if probs else 'тест, всё ок')
        txt += '\nзаготовок: %d, отправлено: %d, годных: %d' % (drafts, sent, good)
        asyncio.run(send(txt))

main()
