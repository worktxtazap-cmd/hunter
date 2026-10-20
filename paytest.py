import json, os, urllib.error, urllib.request
from dotenv import load_dotenv
load_dotenv('.env')
t = os.getenv('CRYPTOPAY_TOKEN', '')
print('длина токена:', len(t), '| начало:', t[:12])
for m in ('getMe', 'getBalance'):
    req = urllib.request.Request('https://pay.crypt.bot/api/' + m, data=b'{}',
                                 headers={'Crypto-Pay-API-Token': t, 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36'})
    try:
        r = urllib.request.urlopen(req, timeout=20)
        print(m, r.status, r.read().decode()[:250])
    except urllib.error.HTTPError as e:
        print(m, e.code, e.read().decode()[:250])
    except Exception as e:
        print(m, type(e).__name__, e)
