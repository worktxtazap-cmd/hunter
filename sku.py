# sku.py - нарезать базу на товарные позиции: 1000, premium, ядро
import csv, os, sqlite3, subprocess, sys
PY = '.venv/bin/python'
NICHE = sys.argv[1]
SRC = 'out/%s_pack' % NICHE
SHORT = {'freelance': 'фриланс', 'crypto': 'крипта', 'infobiz': 'инфобиз',
         'market': 'маркетплейсы', 'smm': 'SMM', 'hr': 'HR',
         'gamble': 'ставки', 'dating': 'дейтинг'}
def rd(name):
    p = os.path.join(SRC, name + '.csv')
    if not os.path.exists(p):
        return None, []
    rows = list(csv.reader(open(p, encoding='utf-8-sig'), delimiter=';'))
    return rows[0], rows[1:]
def num(x):
    try: return int(x or 0)
    except Exception: return 0
def write(tag, head, rows, note):
    d = 'out/%s_pack' % tag
    os.makedirs(d, exist_ok=True)
    with open(d + '/all.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, delimiter=';'); w.writerow(head); w.writerows(rows)
    with open(d + '/all.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join('@' + r[0] for r in rows))
    with open(d + '/README.txt', 'w', encoding='utf-8') as f:
        f.write('%s\nконтактов: %d\n%s\n' % (note, len(rows),
                open(os.path.join(SRC, 'README.txt'), encoding='utf-8').read()))
    subprocess.run([PY, 'preview.py', tag])
    subprocess.run(['cp', d + '/demo.html', 'demo_%s.html' % tag])
    os.makedirs('ready', exist_ok=True)
    subprocess.run(['tar', '-czf', 'ready/%s_pack.tar.gz' % tag, '-C', 'out', '%s_pack' % tag])
    return len(rows)
head, allr = rd('all')
if not allr:
    print('нет сырья', SRC); sys.exit(1)
short = SHORT.get(NICHE, NICHE)
con = sqlite3.connect('hunter.db')
def add(tag, title, price, descr, rows, note):
    n = write(tag, head, rows, note)
    con.execute("insert or replace into products(code,title,price,unit,descr,delivery,active) "
                "values(?,?,?,?,?,?,1)", ('ready_' + tag, title, price, 'база', descr, 'ready'))
    con.commit()
    print('OK', tag, n, '$%g' % price)
con.execute("update products set price=19 where code='ready_%s'" % NICHE)
con.commit()
if len(allr) >= 2000:
    top = sorted(allr, key=lambda r: (-num(r[4]), -num(r[7]), r[5] or 'Z'))[:1000]
    add('%s_1000' % NICHE, short + ' · 1000', 5.0,
        '1000 отборных контактов | сортировка по premium и активности | txt для инвайтера', top,
        'СРЕЗ 1000 лучших контактов')
_, pr = rd('premium')
if len(pr) >= 100:
    add('%s_premium' % NICHE, short + ' · premium', 12.0,
        'только Telegram Premium | платёжеспособная аудитория | txt для инвайтера', pr,
        'СРЕЗ: только Premium')
_, co = rd('core')
if len(co) >= 50:
    add('%s_core' % NICHE, short + ' · ядро', 10.0,
        'ядро: онлайн или недавно и в 2  чатах ниши | самый редкий слой', co,
        'СРЕЗ: ядро')
print('на полке:', con.execute("select count(*) from products where delivery='ready'").fetchone()[0])
con.close()
