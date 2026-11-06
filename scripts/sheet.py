"""抽帧拼接预览图。用法: python sheet.py in out.jpg start end step [cols] [width]"""
import sys, cv2
from PIL import Image, ImageDraw, ImageFont

src, out = sys.argv[1], sys.argv[2]
a, b, st = map(float, sys.argv[3:6])
cols = int(sys.argv[6]) if len(sys.argv) > 6 else 6
w = int(sys.argv[7]) if len(sys.argv) > 7 else 320
cap = cv2.VideoCapture(src)
dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
b = min(b, dur - 0.05)
f = ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf', 16)
ims = []
t = a
while t <= b:
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, fr = cap.read()
    if ok:
        im = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
        im = im.resize((w, int(w * im.height / im.width)))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 62, 20], fill=(0, 0, 0))
        d.text((3, 1), f'{t:.1f}', font=f, fill=(255, 255, 0))
        ims.append(im)
    t += st
h = ims[0].height
rows = (len(ims) + cols - 1) // cols
S = Image.new('RGB', (cols * w, rows * h))
for k, im in enumerate(ims):
    S.paste(im, ((k % cols) * w, (k // cols) * h))
S.save(out, quality=85)
print(len(ims), 'frames', f'{dur:.1f}s')
