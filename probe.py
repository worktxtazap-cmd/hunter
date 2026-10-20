from telethon.sync import TelegramClient
P = '+380665930791'
for name, aid, ah in [('desktop', 2040, 'b18441a1ff607e10a989891a5462e627'),
                      ('android', 6, 'eb06d4abfb49dc3eeb1aeb98ae0f581e')]:
    c = TelegramClient('/tmp/probe_' + name, aid, ah)
    c.connect()
    try:
        r = c.send_code_request(P)
        print(name, '->', type(r.type).__name__, '| next:', type(r.next_type).__name__ if r.next_type else None, '| timeout:', r.timeout)
    except Exception as e:
        print(name, 'ERR', type(e).__name__, str(e)[:100])
    c.disconnect()
