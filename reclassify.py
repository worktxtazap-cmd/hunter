import sqlite3
from collections import defaultdict
from hunter import evaluate

SELLER = ['продам', 'пробив', 'дам парсер', 'выкуп', 'под ключ', 'услуги', 'оказываю', 'недорого', 'прайс', 'портфолио', 'помогу', 'запущу']
HR = ['ищу людей', 'ищем людей', 'ищу сотрудник', 'ищем сотрудник', 'ищем менеджер', 'ищу менеджер',
      'на ворк', 'под процент', 'обучение бесплатно', 'без опыта', 'в кц', 'ищет девуш', 'в команду',
      'кандидат', 'требования', 'оклад', 'график', 'зп']

con = sqlite3.connect("hunter.db", timeout=30)
for col in ("is_ad", "is_seller", "is_hr"):
    try:
        con.execute("alter table hits add column %s integer default 0" % col)
        print("added", col)
    except sqlite3.OperationalError:
        pass

rows = con.execute("select id, text, username from hits").fetchall()
bykey = defaultdict(set)
for i, t, u in rows:
    bykey[' '.join((t or '').lower().split())[:70]].add((u or '').lower())
ads = set(k for k, us in bykey.items() if len(us) >= 3)
print("рекламных копипастов:", len(ads))

keep = adn = sell = hr = drop = 0
for i, t, u in rows:
    low = (t or '').lower()
    is_ad = 1 if ' '.join(low.split())[:70] in ads else 0
    is_seller = 1 if any(m in low for m in SELLER) else 0
    is_hr = 1 if any(m in low for m in HR) else 0
    ev = evaluate(t or "")
    if ev:
        if is_ad: adn += 1; st = 'skip'
        elif is_seller: sell += 1; st = 'skip'
        elif is_hr: hr += 1; st = 'skip'
        else: keep += 1; st = 'new'
        con.execute("update hits set keyword=?, score=?, is_ad=?, is_seller=?, is_hr=?, status=case when sent_at is not null or status='sent' then 'sent' when status='draft' then 'draft' else ? end where id=?", (ev[0], ev[1], is_ad, is_seller, is_hr, st, i))
    else:
        drop += 1
        con.execute("update hits set score=0, is_ad=?, is_seller=?, is_hr=?, status=case when sent_at is not null or status='sent' then 'sent' when status='draft' then 'draft' else 'skip' end where id=?", (is_ad, is_seller, is_hr, i))
con.commit()

print("чистых:", keep, "| реклама:", adn, "| продавец:", sell, "| HR:", hr, "| мимо ниши:", drop)
print("в очереди new:", con.execute("select count(*) from hits where status='new'").fetchone()[0])
print("sent всего:", con.execute("select count(*) from hits where sent_at is not null").fetchone()[0])
for kw, n in con.execute("select keyword, count(*) from hits where status='new' group by keyword order by 2 desc").fetchall():
    print("  ", kw, n)
con.close()
