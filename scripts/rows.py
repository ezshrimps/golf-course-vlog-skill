"""每个时间点一行，抽 offsets 处的帧。用法: python rows.py in out.jpg t1,t2,... [offsets]"""
import sys, cv2
from PIL import Image, ImageDraw, ImageFont

src, out = sys.argv[1], sys.argv[2]
ts = [float(v) for v in sys.argv[3].split(',')]
offs = [float(v) for v in sys.argv[4].split(',')] if len(sys.argv) > 4 else [-1.5, -0.8, -0.3, 0, 0.3, 1.0]
w = 260
cap = cv2.VideoCapture(src)
f = ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf', 15)
rows = []
for t in ts:
    row = []
    for o in offs:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0, t + o) * 1000)
        ok, fr = cap.read()
        im = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)) if ok else Image.new('RGB', (16, 9))
        im = im.resize((w, int(w * 9 / 16)))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 70, 18], fill=(0, 0, 0))
        d.text((3, 1), f'{t + o:.1f}', font=f, fill=(255, 255, 0))
        row.append(im)
    rows.append(row)
h = rows[0][0].height
S = Image.new('RGB', (w * len(offs), h * len(rows)))
for r, row in enumerate(rows):
    for c, im in enumerate(row):
        S.paste(im, (c * w, r * h))
S.save(out, quality=85)
