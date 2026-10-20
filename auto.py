# auto.py - конвейер ниши: найти, вступить, собрать, просеять, упаковать, выложить
import json, os, sqlite3, subprocess, sys
PY = '.venv/bin/python'
NICHE = sys.argv[1]
TITLES = {'crypto': 'крипта и арбитраж', 'infobiz': 'инфобиз и продюсеры',
          'market': 'маркетплейсы и дропшип', 'smm': 'SMM и таргет', 'hr': 'вакансии и HR'}
TARGETS = 'out/%s_targets.json' % NICHE
def run(cmd):
    print('>', cmd[1] if len(cmd) > 1 else cmd[0], flush=True)
    return subprocess.run(cmd)

if not os.path.exists(TARGETS):
    run([PY, 'discover.py', NICHE])
run([PY, 'join2.py', TARGETS])
run([PY, 'pack.py', TARGETS, '1000'])
files = [f for f in os.listdir('out') if f.startswith('%s_targets_' % NICHE) and f.endswith('.csv')]
raw = 'out/' + sorted(files, key=lambda f: os.path.getmtime('out/' + f))[-1]
print('сырьё:', raw)
run([PY, 'clean.py', raw, NICHE])
run([PY, 'preview.py', NICHE])
arc = 'out/%s_pack.tar.gz' % NICHE
run(['tar', '-czf', arc, '-C', 'out', '%s_pack' % NICHE])
os.makedirs('ready', exist_ok=True)
run(['cp', arc, 'ready/%s_pack.tar.gz' % NICHE])
run(['cp', 'out/%s_pack/demo.html' % NICHE, 'demo_%s.html' % NICHE])
rd = open('out/%s_pack/README.txt' % NICHE, encoding='utf-8').read().split(chr(10))[2]
con = sqlite3.connect('hunter.db')
con.execute("insert or replace into products(code,title,price,unit,descr,delivery,active) "
            "values(?,?,?,?,?,?,1)",
            ('ready_%s' % NICHE, 'Готовая база: ' + TITLES.get(NICHE, NICHE), 9.0, 'база', rd, 'ready'))
con.commit()
print('на полке готовых баз:', con.execute("select count(*) from products where delivery='ready'").fetchone()[0])
con.close()
run(['git', 'add', '-A', 'ready'])
run(['git', 'add', 'demo_%s.html' % NICHE])
run(['git', 'commit', '-m', 'ready %s' % NICHE])
run(['git', 'push'])
print('ГОТОВО:', NICHE)
