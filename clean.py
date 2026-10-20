# clean.py - просев сырья в структурированную поставку
import csv, os, random, re, sys
from datetime import date
SRC = sys.argv[1]
TAG = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(SRC).split('_')[0]
OUT = 'out/%s_pack' % TAG
os.makedirs(OUT, exist_ok=True)
GOOD = re.compile(r'^[A-Za-z0-9_]{5,32}$')
rows = list(csv.reader(open(SRC, encoding='utf-8-sig'), delimiter=';'))
head, data = rows[0], rows[1:]
seen, keep = set(), []
st = {'нет ника': 0, 'кривой ник': 0, 'дубль': 0}
for r in data:
    un = r[0].strip()
    if not un:
        st['нет ника'] += 1; continue
    if not GOOD.match(un):
        st['кривой ник'] += 1; continue
    if un.lower() in seen:
        st['дубль'] += 1; continue
    seen.add(un.lower()); keep.append(r)
def num(x):
    try: return int(x or 0)
    except Exception: return 0
core = [r for r in keep if r[5] == 'A' and num(r[7]) >= 2]
prem = [r for r in keep if r[4] == '1']
core.sort(key=lambda r: (-int(r[4] or 0), -num(r[7])))
keep.sort(key=lambda r: (r[5] or 'Z', -int(r[4] or 0), -num(r[7])))
def dump(name, d):
    with open(os.path.join(OUT, name + '.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, delimiter=';'); w.writerow(head); w.writerows(d)
    with open(os.path.join(OUT, name + '.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join('@' + r[0] for r in d))
dump('all', keep); dump('core', core); dump('premium', prem)
with open(os.path.join(OUT, 'README.txt'), 'w', encoding='utf-8') as f:
    f.write('БАЗА %s\nдата: %s\n' % (TAG, date.today()))
    f.write('всего %d | ядро A/2+ %d | premium %d\n' % (len(keep), len(core), len(prem)))
    f.write('с именем %d из %d | источников %d\n' % (
        sum(1 for r in keep if r[2].strip()), len(keep), len(set(x for r in keep for x in r[8].split(';') if x))))
    f.write('\nall.csv - вся база\ncore.csv - онлайн/недавно и в 2+ чатах\n')
    f.write('premium.csv - Telegram Premium\n*.txt - @ники для инвайтера\n')
    f.write('\nпросев: ' + str(st) + '\n')
smp = random.sample(keep, min(20, len(keep)))
open(os.path.join(OUT, 'check.txt'), 'w', encoding='utf-8').write(
    '\n'.join('@' + r[0] for r in smp))
print('ГОТОВО', OUT, '| all', len(keep), '| core', len(core),
      '| premium', len(prem), '| просев', st)
