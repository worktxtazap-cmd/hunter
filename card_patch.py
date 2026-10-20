p = 'shop.py'
s = open(p, encoding='utf-8').read()

a = """        txt = box('hunter pay · касса', ['базы участников · парсинг · боты'])
        txt += chr(10) + chr(10) + 'выбирай, что нужно — счёт придёт сюда же'"""
b = """        txt = ''"""
assert s.count(a) == 1, s.count(a)
s = s.replace(a, b, 1)

a2 = """        if edit:
            try:
                await edit.edit(caption=txt, buttons=menu_kb())
            except Exception:
                await edit.edit(txt, buttons=menu_kb())
        elif os.path.exists(PHOTO):
            await client.send_file(uid, PHOTO, caption=txt, buttons=menu_kb())
        else:
            await client.send_message(uid, txt, buttons=menu_kb())"""
b2 = """        cap = txt if txt else None
        if edit:
            try:
                await edit.edit(caption=cap, buttons=menu_kb())
            except Exception:
                await edit.edit(txt, buttons=menu_kb())
        elif os.path.exists(PHOTO):
            await client.send_file(uid, PHOTO, caption=cap, buttons=menu_kb())
        else:
            await client.send_message(uid, txt, buttons=menu_kb())"""
assert s.count(a2) == 1, s.count(a2)
s = s.replace(a2, b2, 1)

open(p, 'w', encoding='utf-8').write(s)
print('текст убран, остался креатив и кнопки')
