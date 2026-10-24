# make_banner.py - креатив: фон из assets/bg.png + наш текст
import os, sqlite3
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
BG = (14, 22, 33); GOLD = (217, 169, 74); WHITE = (238, 243, 248)
GRAY = (150, 170, 190); DARK = (16, 22, 30)
FB = '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf'
FR = '/usr/share/fonts/truetype/freefont/FreeSans.ttf'
LABEL = {'base1': 'база · 1 чат', 'base3': 'база · 3 чата', 'base10': 'база · 10 чатов',
         'clean': 'чистка и сегмент', 'bot': 'телеграм-бот'}
ORDER = ['base1', 'base3', 'base10', 'clean', 'bot']

def F(p, s):
    return ImageFont.truetype(p, s)

def center(d, text, f, fill, y, space=0):
    total = sum(d.textlength(c, font=f) + space for c in text) - space
    x = (W - total) / 2
    for c in text:
        d.text((x, y), c, font=f, fill=fill)
        x += d.textlength(c, font=f) + space

def bg_image():
    if os.path.exists('assets/bg.png'):
        im = Image.open('assets/bg.png').convert('RGB')
        k = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * k) + 1, int(im.height * k) + 1), Image.LANCZOS)
        x = (im.width - W) // 2
        y = (im.height - H) // 2
        im = im.crop((x, y, x + W, y + H))
        veil = Image.new('RGB', (W, H), BG)
        return Image.blend(im, veil, 0.45)
    return Image.new('RGB', (W, H), BG)

def main():
    img = bg_image()
    d = ImageDraw.Draw(img)
    f_t, f_s, f_r, f_p, f_b, f_m = F(FB, 104), F(FR, 38), F(FR, 48), F(FB, 48), F(FB, 42), F(FR, 34)

    d.line([(90, 96), (W - 90, 96)], fill=(60, 80, 100), width=2)
    center(d, 'HUNTER PAY', f_t, GOLD, 200, space=10)
    d.line([(W / 2 - 150, 372), (W / 2 + 150, 372)], fill=GOLD, width=3)
    center(d, 'базы участников Telegram', f_s, GRAY, 412)

    con = sqlite3.connect('hunter.db', timeout=20)
    rows = []
    for code in ORDER:
        r = con.execute("select title, price from products where code=?", (code,)).fetchone()
        if r:
            price = '+$%g' % r[1] if code == 'clean' else ('от $%g' % r[1] if code == 'bot' else '$%g' % r[1])
            rows.append((LABEL.get(code, r[0]), price))
    con.close()

    y = 660
    for label, price in rows:
        d.rectangle([110, y + 22, 118, y + 30], fill=GOLD)
        d.text((142, y), label, font=f_r, fill=WHITE)
        pw = d.textlength(price, font=f_p)
        d.text((W - 110 - pw, y), price, font=f_p, fill=GOLD)
        x = 142 + d.textlength(label, font=f_r) + 26
        x2 = W - 110 - pw - 26
        while x < x2:
            d.text((x, y + 22), '·', font=f_r, fill=(90, 110, 130))
            x += 26
        y += 122

    bx, by, bw, bh = 140, 1630, W - 280, 122
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=20, fill=GOLD)
    center(d, 'ЗАКАЗАТЬ', f_b, DARK, by + 36, space=6)
    center(d, '@hunter_pay_bot', f_m, GRAY, 1800)
    d.line([(90, 1832), (W - 90, 1832)], fill=(60, 80, 100), width=2)

    os.makedirs('assets', exist_ok=True)
    img.save('assets/banner.png')
    print('креатив:', img.size)

main()
