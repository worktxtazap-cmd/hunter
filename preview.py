# preview.py - demo.html: превью базы со статистикой
import csv, os, sys, html
from datetime import date
TAG = sys.argv[1]
OUT = 'out/%s_pack' % TAG
def rd(n):
    p = os.path.join(OUT, n)
    return list(csv.reader(open(p, encoding='utf-8-sig'), delimiter=';'))[1:] if os.path.exists(p) else []
allr, corer, premr = rd('all.csv'), rd('core.csv'), rd('premium.csv')
def rows(d, lim=50):
    return '\n'.join('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
        html.escape('@' + r[0]), html.escape(r[2] or '-'),
        'да' if r[4] == '1' else '', r[7]) for r in d[:lim])
tpl = """<!doctype html><meta charset=utf-8>
<title>База %(tag)s</title>
<style>
body{background:#0e1621;color:#eef3f8;font:15px/1.5 sans-serif;margin:0;padding:24px}
h1{color:#d9a94a;font-size:25px;margin:0 0 6px}
.sub{color:#96aabe;margin-bottom:18px}
.stats{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:20px}
.card{background:#131d2b;border:1px solid #23303f;border-radius:12px;padding:12px 16px;min-width:118px}
.card b{display:block;color:#d9a94a;font-size:22px}
.card span{color:#96aabe;font-size:12px}
table{border-collapse:collapse;width:100%%;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #1e2a38}
th{color:#d9a94a}
.note{color:#96aabe;font-size:13px;margin-top:14px}
</style>
<h1>HUNTER PAY — база «%(tag)s»</h1>
<div class=sub>дата сбора %(date)s · групп-источников: %(src)d</div>
<div class=stats>
<div class=card><b>%(all)d</b><span>всего контактов</span></div>
<div class=card><b>%(core)d</b><span>ядро: активные, 2+ чата</span></div>
<div class=card><b>%(prem)d</b><span>Telegram Premium</span></div>
</div>
<table><tr><th>ник</th><th>имя</th><th>premium</th><th>чатов</th></tr>
%(rows)s
</table>
<div class=note>показаны первые 50 из %(all)d · @hunter_pay_bot</div>
"""
srcs = set(x for r in allr for x in r[8].split(';') if x)
open(os.path.join(OUT, 'demo.html'), 'w', encoding='utf-8').write(tpl % dict(
    tag=TAG, date=date.today(), src=len(srcs), all=len(allr),
    core=len(corer), prem=len(premr), rows=rows(corer or allr)))
print('demo.html готов:', len(allr), 'всего /', len(corer), 'ядро')
