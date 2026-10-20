# креатив без цен: только бренд и оффер, без нарисованной кнопки
import os
from PIL import Image, ImageDraw, ImageFont
GOLD=(217,169,74); WHITE=(238,243,248); GRAY=(150,170,190); BG=(14,22,33)
FB='/usr/share/fonts/truetype/freefont/FreeSansBold.ttf'
FR='/usr/share/fonts/truetype/freefont/FreeSans.ttf'
LINES=['контакты с юзернеймами','готово под рассылку и найм','демо — бесплатно']
def F(p,s): return ImageFont.truetype(p,s)
def center(d,t,f,fill,y,W,space=0):
    tot=sum(d.textlength(c,font=f)+space for c in t)-space
    x=(W-tot)/2
    for c in t:
        d.text((x,y),c,font=f,fill=fill)
        x+=d.textlength(c,font=f)+space
def bg_image(W,H):
    if os.path.exists('assets/bg.png'):
        im=Image.open('assets/bg.png').convert('RGB')
        k=max(W/im.width,H/im.height)
        im=im.resize((int(im.width*k)+1,int(im.height*k)+1),Image.LANCZOS)
        x=(im.width-W)//2; y=(im.height-H)//2
        im=im.crop((x,y,x+W,y+H))
        return Image.blend(im,Image.new('RGB',(W,H),BG),0.45)
    return Image.new('RGB',(W,H),BG)
def build(W,H,path):
    img=bg_image(W,H); d=ImageDraw.Draw(img)
    ft=F(FB,104); fs=F(FR,38); fl=F(FR,46); fm=F(FR,34)
    ty=int(H*0.145)
    d.line([(90,96),(W-90,96)],fill=(60,80,100),width=2)
    center(d,'HUNTER PAY',ft,GOLD,ty,W,space=10)
    d.line([(W/2-150,ty+172),(W/2+150,ty+172)],fill=GOLD,width=3)
    center(d,'базы участников Telegram-чатов',fs,GRAY,ty+212,W)
    y=int(H*0.46)
    for ln in LINES:
        center(d,ln,fl,WHITE,y,W); y+=int(H*0.072)
    center(d,'@hunter_pay_bot',fm,GRAY,H-130,W)
    d.line([(90,H-78),(W-90,H-78)],fill=(60,80,100),width=2)
    img.save(path); print(path,img.size)
os.makedirs('assets',exist_ok=True)
build(1080,1350,'assets/banner.png')
build(1080,1080,'assets/ad_square.png')
