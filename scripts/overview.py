"""全部片段缩略图总览（每片段一行 7 帧），用于人工分洞。输出 sh/ov_*.jpg"""
import os, cv2
from PIL import Image, ImageDraw, ImageFont
import project as P
os.makedirs('sh', exist_ok=True)
f = ImageFont.truetype(P.FONTS + 'bahnschrift.ttf', 16)
w, h, cols = 230, 130, 7
rows = []
for c in P.clips():
    cap = cv2.VideoCapture(P.lrf(c)); n = cap.get(cv2.CAP_PROP_FRAME_COUNT); fps = cap.get(cv2.CAP_PROP_FPS)
    dur = n / fps; row = []
    for k in range(cols):
        t = dur * (k + 0.5) / cols
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, fr = cap.read()
        im = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)).resize((w, h)) if ok else Image.new('RGB', (w, h))
        d = ImageDraw.Draw(im); lab = (c + ' ' if k == 0 else '') + f'{t:.0f}'
        d.rectangle([0, 0, 9 * len(lab) + 4, 18], fill=(0, 0, 0)); d.text((2, 0), lab, font=f, fill=(255, 255, 0))
        row.append(im)
    rows.append(row)
per = 18
for s in range(0, len(rows), per):
    R = rows[s:s + per]
    S = Image.new('RGB', (w * cols, h * len(R)))
    for r, row in enumerate(R):
        for c, im in enumerate(row): S.paste(im, (c * w, r * h))
    S.save(f'sh/ov_{s // per}.jpg', quality=80)
print('ok')
