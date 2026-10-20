import asyncio
import hashlib
import os
import re
import sqlite3
from datetime import datetime, timezone

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError

import config

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_NAME = os.getenv("SESSION_NAME", "hunter")
NOTIFY_TARGET = os.getenv("NOTIFY_TARGET", "me")
DB_PATH = "hunter.db"

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE IF NOT EXISTS hits (id INTEGER PRIMARY KEY AUTOINCREMENT, chat TEXT NOT NULL, msg_id INTEGER NOT NULL, user_id INTEGER, username TEXT, text TEXT, keyword TEXT, score INTEGER DEFAULT 0, status TEXT DEFAULT 'new', sent_at TEXT, found_at TEXT, UNIQUE(chat, msg_id))")
    con.execute("CREATE TABLE IF NOT EXISTS seen (uid INTEGER NOT NULL, h TEXT NOT NULL, PRIMARY KEY (uid, h))")
    for ddl in ("ALTER TABLE hits ADD COLUMN score INTEGER DEFAULT 0", "ALTER TABLE hits ADD COLUMN status TEXT DEFAULT 'new'", "ALTER TABLE hits ADD COLUMN sent_at TEXT"):
        try:
            con.execute(ddl)
        except sqlite3.OperationalError:
            pass
    if con.execute("SELECT count(*) FROM seen").fetchone()[0] == 0:
        for uid, text in con.execute("SELECT user_id, text FROM hits").fetchall():
            con.execute("INSERT OR IGNORE INTO seen (uid, h) VALUES (?, ?)", (uid or 0, digest(text)))
    con.commit()
    con.close()


def norm(t):
    t = t.lower()
    t = re.sub(r"https?://\S ", " ", t)
    t = re.sub(r"[^0-9a-zа-яёіїєґ\s]", " ", t)
    return re.sub(r"\s ", " ", t).strip()


def digest(t):
    return hashlib.md5(norm(t).encode("utf-8")).hexdigest()


def evaluate(text):
    low = text.lower()
    for s in config.STOP_KEYWORDS:
        if s in low:
            return None
    score = 0
    kw = None
    for k in config.DEMAND_KEYWORDS:
        if k in low:
            score = score   3
            if kw is None:
                kw = k
    for m in config.DEMAND_MARKERS:
        if m in low:
            score = score   1
            break
    for a in config.AD_MARKERS:
        if a in low:
            score = score - 1
            break
    if score < config.MIN_SCORE:
        return None
    return (kw or "спрос", score)


def save_hit(chat, msg_id, user_id, username, text, keyword, score):
    con = sqlite3.connect(DB_PATH)
    try:
        try:
            con.execute("INSERT INTO seen (uid, h) VALUES (?, ?)", (user_id or 0, digest(text)))
        except sqlite3.IntegrityError:
            return False
        con.execute("INSERT INTO hits (chat, msg_id, user_id, username, text, keyword, score, status, found_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?)", (chat, msg_id, user_id, username, text, keyword, score, datetime.now(timezone.utc).isoformat(timespec="seconds")))
        con.commit()
        return True
    except sqlite3.IntegrityError:
        return False
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
        print("["   str(source)   "]", e)
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
        if save_hit(str(source), msg.id, uid, username, text, kw, score):
            found.append((username, kw, score, text))
    return found


async def notify(found):
    if not found:
        return
    lines = ["Новых заявок: "   str(len(found))]
    for username, kw, score, text in found:
        lines.append("")
        lines.append("@"   username if username else "без юзернейма")
        lines.append("ключ: "   str(kw)   " | "   str(score))
        lines.append(text[:200])
        if username:
            lines.append("https://t.me/"   username)
    try:
        await client.send_message(NOTIFY_TARGET, "\n".join(lines))
    except Exception as e:
        print("notify", e)


async def main():
    init_db()
    await client.start()
    print("Охотник запущен. Источников: "   str(len(config.SOURCES)))
    while True:
        found = []
        for source in config.SOURCES:
            found.extend(await scan(source))
        await notify(found)
        print("цикл ок, новых: "   str(len(found)))
        await asyncio.sleep(config.POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
