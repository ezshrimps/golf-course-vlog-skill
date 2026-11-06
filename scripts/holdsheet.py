"""收杆停留时长核对图。用法: python holdsheet.py 最小秒 最大秒"""
import json, cv2, sys
from PIL import Image, ImageDraw, ImageFont
import project as P
H = json.load(open('hold.json')); E = {(e['clip'], round(e['t'], 2)): e for e in json.load(open('events.json'))}
lo, hi = float(sys.argv[1]), float(sys.argv[2])
sel = sorted([h for h in H if lo <= h['hold'] < hi], key=lambda h: -h['hold'])
f = ImageFont.truetype(P.FONTS + 'bahnschrift.ttf', 15)
offs = [0.4, 1.2, 2.0, 3.0, 4.0]; cw, ch = 150, 200; rows = []
for h in sel:
    e = E[(h['clip'], round(h['t'], 2))]
    cap = cv2.VideoCapture(P.lrf(h['clip']))
    x0, y0, x1, y1 = e['box']; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; hh = max(80, (y1 - y0) * 1.5); w = hh * cw / ch
    row = []
    for o in offs:
        cap.set(cv2.CAP_PROP_POS_MSEC, (h['t_imp'] + o) * 1000); ok, fr = cap.read()
        im = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)).crop((int(cx - w / 2), int(cy - hh / 2), int(cx + w / 2), int(cy + hh / 2))).resize((cw, ch))
        row.append(im)
    lab = Image.new('RGB', (110, ch), (20, 20, 20)); d = ImageDraw.Draw(lab)
    d.text((5, 5), f'{h["clip"]} {h["t"]:.0f}', font=f, fill=(255, 255, 0)); d.text((5, 28), f'hold {h["hold"]}', font=f, fill=(0, 255, 0))
    rows.append([lab] + row)
per = 13
for s in range(0, len(rows), per):
    R = rows[s:s + per]; S = Image.new('RGB', (110 + cw * 5, ch * len(R)))
    for r, row in enumerate(R):
        x = 0
        for im in row: S.paste(im, (x, r * ch)); x += im.width
    S.save(f'sh/hold_{lo}_{s // per}.jpg', quality=80)
print(len(rows))
