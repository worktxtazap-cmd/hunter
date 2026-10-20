import csv, html, os

src = 'demo_freelance_chatik0.csv'
rows = list(csv.reader(open(src, encoding='utf-8-sig'), delimiter=';'))
head, body = rows[0], rows[1:]
name = os.path.basename(src).replace('demo_', '').replace('.csv', '')
a = sum(1 for r in body if r[4] == 'A')
b = sum(1 for r in body if r[4] == 'B')
u = sum(1 for r in body if r[1])

o = []
o.append('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
o.append('<title>Пример базы: %s</title>' % html.escape(name))
o.append('<style>body{font:14px/1.6 -apple-system,Segoe UI,sans-serif;margin:18px;color:#111}'
         'table{border-collapse:collapse;width:100%}td,th{border:1px solid #e2e2e2;padding:3px 7px;'
         'text-align:left;font-size:13px}th{background:#f4f4f4}h1{font-size:19px;margin:0 0 8px}'
         '.box{background:#f8f8f8;border:1px solid #e2e2e2;padding:10px 12px;border-radius:6px;margin:10px 0}'
         'small{color:#666}</style>')
o.append('<h1>Пример базы: чат %s</h1>' % html.escape(name))
o.append('<div class="box">Всего контактов: <b>%d</b> &middot; с юзернеймом: <b>%d</b> &middot; активных (A): <b>%d</b>'
         '<br><small>Боты, удалённые и дубли вычищены. Сегмент: A — онлайн или недавно, B — на этой неделе, '
         'C — в этом месяце, D — дата последнего визита. Показаны первые 80 строк.</small></div>' % (len(body), u, a))
o.append('<table><tr>' + ''.join('<th>%s</th>' % html.escape(c) for c in head) + '</tr>')
for r in body[:80]:
    o.append('<tr>' + ''.join('<td>%s</td>' % html.escape(c) for c in r) + '</tr>')
o.append('</table>')
o.append('<div class="box"><b>Цены:</b> 1 чат — $5, 3 чата — $12, 10 чатов — $30. '
         'Чистка и сегмент — +$5. Срок 1-3 часа. Оплата USDT/TON или карта. Пишите: @softzoneua2026</div>')
open('demo_preview.html', 'w', encoding='utf-8').write('\n'.join(o))
print('превью готово, строк:', min(80, len(body)))
