import asyncio
import hashlib
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError

import config
import templates

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

SESSION_NAME = os.getenv("SESSION_NAME", "hunter")
NOTIFY_TARGET = os.getenv("NOTIFY_TARGET", "me")
NOTIFY_MAX = int(os.getenv("NOTIFY_MAX", "6"))
DB_PATH = "hunter.db"

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db():
    con = db()
    con.execute("CREATE TABLE IF NOT EXISTS hits (id INTEGER PRIMARY KEY AUTOINCREMENT, chat TEXT NOT NULL, msg_id INTEGER NOT NULL, user_id INTEGER, username TEXT, text TEXT, keyword TEXT, score INTEGER DEFAULT 0, status TEXT DEFAULT 'new', sent_at TEXT, found_at TEXT, UNIQUE(chat, msg_id))")
    con.execute("CREATE TABLE IF NOT EXISTS seen (uid INTEGER NOT NULL, h TEXT NOT NULL, PRIMARY KEY (uid, h))")
    for ddl in ("ALTER TABLE hits ADD COLUMN score INTEGER DEFAULT 0", "ALTER TABLE hits ADD COLUMN status TEXT DEFAULT 'new'", "ALTER TABLE hits ADD COLUMN sent_at TEXT"):
        try:
            con.execute(ddl)
        except sqlite3.OperationalError:
            pass
    con.commit()
    con.close()


def norm(t):
    t = t.lower()
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"[^0-9a-zа-яёіїєґ\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def digest(t):
    return hashlib.md5(norm(t).encode("utf-8")).hexdigest()


def evaluate(text):
    low = re.sub(r"[#_*·•|]", "", text.lower())
    for s in config.STOP_KEYWORDS:
        if s in low:
            return None
    strong = [k for k in config.DEMAND_STRONG if k in low]
    topic = [k for k in config.DEMAND_TOPIC if k in low]
    ad = [a for a in config.AD_MARKERS if a in low]
    if not strong and len(topic) < 2:
        return None
    score = 0
    if strong:
        score += 7 + min(len(strong) - 1, 2)
    if topic:
        score += 3 + min(len(topic) - 1, 2)
    if re.search(config.PRICE_RE, low):
        score -= 2
    score -= min(len(ad), 3)
    if low.count("\n") >= 6:
        score -= 1
    if score < config.MIN_SCORE:
        return None
    return (strong[0] if strong else topic[0], score)


def save_hit(chat, msg_id, user_id, username, text, keyword, score):
    con = db()
    try:
        cur = con.execute("INSERT OR IGNORE INTO seen (uid, h) VALUES (?, ?)", (user_id or 0, digest(text)))
        if cur.rowcount == 0:
            return None
        cur = con.execute("INSERT OR IGNORE INTO hits (chat, msg_id, user_id, username, text, keyword, score, status, found_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?)", (chat, msg_id, user_id, username, text, keyword, score, datetime.now(timezone.utc).isoformat(timespec="seconds")))
        con.commit()
        return cur.lastrowid if cur.rowcount > 0 else None
    finally:
        con.close()


async def scan(source):
    found = []
    try:
        messages = await client.get_messages(source, limit=config.MESSAGES_PER_CHAT)
    except FloodWaitError as e:
        print("flood", e.seconds)
        await asyncio.sleep(e.seconds)
        return found
    except Exception as e:
        print("[" + str(source) + "]", e)
        return found
    for msg in messages:
        if msg.out or not msg.message:
            continue
        text = msg.message
        if len(text) < config.MIN_TEXT_LEN or len(text) > config.MAX_TEXT_LEN:
            continue
        ev = evaluate(text)
        if not ev:
            continue
        kw, score = ev
        try:
            sender = await msg.get_sender()
        except Exception:
            sender = None
        username = getattr(sender, "username", None)
        uid = getattr(sender, "id", None)
        hid = save_hit(str(source), msg.id, uid, username, text, kw, score)
        if hid:
            found.append((username, kw, score, text, str(source), msg.id, hid))
    return found


async def notify(found):
    hits = [f for f in found if f[0]]
    if not hits:
        return
    hits.sort(key=lambda x: -x[2])
    hits = hits[:NOTIFY_MAX]
    con = db()
    for username, kw, score, text, chat, mid, hid in hits:
        snip = " ".join((text or "").split())[:120]
        body = "https://t.me/%s/%s\n@%s\nчто искал: %s\n\n%s\n\n%s" % (chat, mid, username, snip, templates.pick(kw, text, chat), templates.LINK)
        ok = False
        try:
            await client.send_message(NOTIFY_TARGET, body)
            ok = True
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 3)
            try:
                await client.send_message(NOTIFY_TARGET, body)
                ok = True
            except Exception as e2:
                print("notify", e2)
        except Exception as e:
            print("notify", e)
        if ok:
            con.execute("update hits set status='hot' where id=?", (hid,))
        await asyncio.sleep(1)
    con.commit()
    con.close()


async def main():
    init_db()
    await client.start()
    once = len(sys.argv) > 1 and sys.argv[1] == "--once"
    print("hunter started. sources: " + str(len(config.SOURCES)))
    while True:
        found = []
        for source in config.SOURCES:
            found.extend(await scan(source))
        await notify(found)
        print("cycle ok, new: " + str(len(found)))
        if once:
            break
        await asyncio.sleep(config.POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
