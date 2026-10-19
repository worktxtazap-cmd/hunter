import asyncio
import os
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
    con.execute("""
        CREATE TABLE IF NOT EXISTS hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat TEXT NOT NULL,
            msg_id INTEGER NOT NULL,
            user_id INTEGER,
            username TEXT,
            text TEXT,
            keyword TEXT,
            found_at TEXT,
            UNIQUE(chat, msg_id)
        )
    """)
    con.commit()
    con.close()


def save_hit(chat, msg_id, user_id, username, text, keyword):
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(
            "INSERT INTO hits (chat, msg_id, user_id, username, text, keyword, found_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (chat, msg_id, user_id, username, text, keyword,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        con.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        con.close()


def find_keyword(text):
    low = text.lower()
    for stop in config.STOP_KEYWORDS:
        if stop in low:
            return None
    for kw in config.DEMAND_KEYWORDS:
        if kw in low:
            return kw
    return None


async def scan(source):
    hits = []
    try:
        messages = await client.get_messages(source, limit=config.MESSAGES_PER_CHAT)
    except FloodWaitError as e:
        print(f"flood wait {e.seconds}s")
        await asyncio.sleep(e.seconds)
        return hits
    except Exception as e:
        print(f"[{source}] {e}")
        return hits

    for msg in messages:
        if msg.out or not msg.message or len(msg.message) < 15:
            continue
        kw = find_keyword(msg.message)
        if not kw:
            continue
        try:
            sender = await msg.get_sender()
        except Exception:
            sender = None
        username = getattr(sender, "username", None)
        uid = getattr(sender, "id", None)
        if save_hit(str(source), msg.id, uid, username, msg.message, kw):
            hits.append((username, kw, msg.message))
    return hits


async def notify(hits):
    if not hits:
        return
    lines = [f"Новых заявок: {len(hits)}"]
    for username, kw, text in hits:
        lines.append("")
        lines.append(f"@{username}" if username else "без юзернейма")
        lines.append(f"ключ: {kw}")
        lines.append(text[:200])
        if username:
            lines.append(f"https://t.me/{username}")
    await client.send_message(NOTIFY_TARGET, "\n".join(lines))


async def main():
    init_db()
    await client.start()
    print(f"Охотник запущен. Источников: {len(config.SOURCES)}")
    while True:
        all_hits = []
        for source in config.SOURCES:
            all_hits.extend(await scan(source))
        await notify(all_hits)
        await asyncio.sleep(config.POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
