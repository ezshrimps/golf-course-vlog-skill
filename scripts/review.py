"""挥杆核对图：每个事件一行，人物附近裁剪。用法: python review.py clipA clipB"""
import sys, json, cv2
from PIL import Image, ImageDraw, ImageFont

import project as P
lo, hi = sys.argv[1], sys.argv[2]
import os; os.makedirs('sh', exist_ok=True)
ev = [e for e in json.load(open('swings.json')) if lo <= e['clip'] <= hi and not e.get('audio_only')]
f = ImageFont.truetype(P.FONTS + 'bahnschrift.ttf', 15)
offs = [-0.9, -0.35, 0, 0.35, 1.0]
cw, ch = 170, 220
caps = {}
rows = []
for n, e in enumerate(ev):
    p = P.lrf(e['clip'])
    cap = caps.setdefault(p, cv2.VideoCapture(p))
    x0, y0, x1, y1 = e['box']
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    h = max(80, (y1 - y0) * 1.5)
    w = h * cw / ch
    row = []
    for o in offs:
        cap.set(cv2.CAP_PROP_POS_MSEC, (e['t'] + o) * 1000)
        ok, fr = cap.read()
        im = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)) if ok else Image.new('RGB', (cw, ch))
        im = im.crop((int(cx - w / 2), int(cy - h / 2), int(cx + w / 2), int(cy + h / 2))).resize((cw, ch))
        row.append(im)
    lab = Image.new('RGB', (150, ch), (20, 20, 20))
    d = ImageDraw.Draw(lab)
    d.text((6, 6), f'#{n} {e["clip"]}', font=f, fill=(255, 255, 0))
    d.text((6, 28), f't={e["t"]:.1f}', font=f, fill=(255, 255, 255))
    d.text((6, 50), 'HIT' if e['hit'] else 'no hit', font=f, fill=(0, 255, 0) if e['hit'] else (255, 120, 120))
    d.text((6, 72), e['leg'], font=f, fill=(255, 255, 255))
    rows.append([lab] + row)
per = 12
for s in range(0, len(rows), per):
    R = rows[s:s + per]
    S = Image.new('RGB', (150 + cw * len(offs), ch * len(R)))
    for r, row in enumerate(R):
        x = 0
        for im in row:
            S.paste(im, (x, r * ch)); x += im.width
    S.save(f'sh/rv_{lo}_{s // per}.jpg', quality=82)
print(len(ev), 'events')
