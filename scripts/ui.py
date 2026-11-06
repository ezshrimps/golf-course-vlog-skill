"""Vlog UI 叠加层（1920x1080 RGBA）。"""
import math, json
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import project as P

W, H = 1920, 1080
FD = P.FONTS
ACC = (196, 255, 77)       # 荧光绿主色
GOLD = (255, 200, 60)
WHITE = (255, 255, 255)
PANEL = (12, 16, 20)

@lru_cache(None)
def F(size, kind='b'):
    if kind == 'zh':
        return ImageFont.truetype(FD + 'msyhbd.ttc', size)
    if kind == 'zhl':
        return ImageFont.truetype(FD + 'msyh.ttc', size)
    f = ImageFont.truetype(FD + 'bahnschrift.ttf', size)
    try:
        f.set_variation_by_name({'b': 'Bold', 'sb': 'SemiBold', 'r': 'Regular', 'l': 'Light',
                                 'c': 'SemiBold Condensed'}[kind])
    except Exception:
        pass
    return f

SCORE = P.SCORE
ROUTE = P.ROUTE

def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3

def panel(size, radius=18, alpha=170):
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius, fill=PANEL + (alpha,))
    d.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius, outline=(255, 255, 255, 38), width=1)
    return im

def shadow_text(d, xy, text, font, fill, anchor='la', sh=2):
    d.text((xy[0] + sh, xy[1] + sh), text, font=font, fill=(0, 0, 0, 120), anchor=anchor)
    d.text(xy, text, font=font, fill=fill, anchor=anchor)

# ---------- 常驻 HUD（左上） ----------
@lru_cache(64)
def hud(course, hole, clock):
    """course: 九洞名, hole: int, clock: '1:44 PM'"""
    sc = SCORE[course]
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    p = panel((430, 176))
    d = ImageDraw.Draw(p)
    d.text((26, 22), P.LABEL, font=F(17, 'sb'), fill=(255, 255, 255, 170))
    d.text((404, 22), clock, font=F(17, 'sb'), fill=(255, 255, 255, 170), anchor='ra')
    # 课程标签
    d.rounded_rectangle([26, 52, 26 + 12 + d.textlength(course, font=F(16, 'b')) + 12, 78], 6, fill=ACC + (255,))
    d.text((38, 55), course, font=F(16, 'b'), fill=(10, 14, 10))
    d.text((24, 82), 'HOLE', font=F(20, 'sb'), fill=(255, 255, 255, 200))
    d.text((24, 98), f'{hole}', font=F(66, 'b'), fill=WHITE)
    x0 = 130
    stats = [('PAR', sc['par'][hole - 1]), ('YDS', sc['white'][hole - 1]), ('HCP', sc['hcp'][hole - 1])]
    for k, (lab, v) in enumerate(stats):
        x = x0 + k * 96
        d.text((x, 92), lab, font=F(16, 'sb'), fill=(255, 255, 255, 140))
        d.text((x, 110), str(v), font=F(40, 'b'), fill=WHITE)
    # 进度条：每洞一格，换九洞处留空隙
    cur = ROUTE.index((course, hole))
    step = min(25, 370 / len(ROUTE))
    gap = 0
    for k in range(len(ROUTE)):
        if k and ROUTE[k][0] != ROUTE[k - 1][0]:
            gap += 8
        x = 26 + k * step + gap
        col = ACC + (255,) if k == cur else ((255, 255, 255, 200) if k < cur else (255, 255, 255, 55))
        d.rounded_rectangle([x, 160, x + step - 4, 165], 2, fill=col)
    im.alpha_composite(p, (48, 44))
    return im

# ---------- 球洞开场卡（右侧） ----------
@lru_cache(16)
def hole_card(course, hole):
    sc = SCORE[course]
    mp = Image.open(f'maps/{course}_{hole}.png').convert('RGBA')
    mp = mp.resize((int(mp.width * 0.78), int(mp.height * 0.78)), Image.LANCZOS)
    cw, ch = 470, 940
    p = panel((cw, ch), 24, 190)
    d = ImageDraw.Draw(p)
    d.text((34, 30), f'{course} COURSE', font=F(20, 'sb'), fill=ACC + (255,))
    d.text((30, 52), f'HOLE {hole}', font=F(84, 'b'), fill=WHITE)
    d.text((34, 148), f'PAR {sc["par"][hole-1]}', font=F(30, 'b'), fill=WHITE)
    d.text((160, 154), f'HANDICAP {sc["hcp"][hole-1]}', font=F(20, 'sb'), fill=(255, 255, 255, 160))
    d.line([(34, 196), (cw - 34, 196)], fill=(255, 255, 255, 40), width=1)
    for k, (lab, key, col) in enumerate([('BLUE', 'blue', (90, 150, 255)), ('WHITE', 'white', (240, 240, 240))]):
        x = 34 + k * 200
        d.ellipse([x, 216, x + 12, 228], fill=col + (255,))
        d.text((x + 20, 212), lab, font=F(18, 'sb'), fill=(255, 255, 255, 160))
        d.text((x, 236), f'{sc[key][hole-1]}', font=F(40, 'b'), fill=WHITE)
        d.text((x + d.textlength(f'{sc[key][hole-1]}', font=F(40, 'b')) + 6, 254), 'YDS', font=F(16, 'sb'),
               fill=(255, 255, 255, 140))
    p.alpha_composite(mp, ((cw - mp.width) // 2, ch - mp.height - 16))
    return p

def hole_card_frame(course, hole, t, dur=5.5):
    """t: 卡片出现后的秒数；滑入 + 停留 + 滑出"""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    if t < 0 or t > dur:
        return None
    c = hole_card(course, hole)
    a = ease(t / 0.6) * (1 - ease((t - (dur - 0.5)) / 0.5))
    x = int(W - 48 - c.width + (1 - ease(t / 0.6)) * 120) if t < dur - 0.5 else \
        int(W - 48 - c.width + ease((t - (dur - 0.5)) / 0.5) * 120)
    cc = c.copy()
    cc.putalpha(cc.getchannel('A').point(lambda v: int(v * a)))
    im.alpha_composite(cc, (x, (H - c.height) // 2))
    return im

# ---------- 小标签（左下） ----------
def tag_frame(text, sub, t, dur, color=ACC):
    if t < 0 or t > dur:
        return None
    a = ease(t / 0.35) * (1 - ease((t - dur + 0.35) / 0.35))
    f1, f2 = F(30, 'b'), F(19, 'zhl') if any(ord(ch) > 255 for ch in sub) else F(19, 'sb')
    w = int(max(ImageDraw.Draw(Image.new('L', (1, 1))).textlength(text, font=f1),
                ImageDraw.Draw(Image.new('L', (1, 1))).textlength(sub, font=f2)) + 64)
    p = panel((w, 92 if sub else 64), 14, 175)
    d = ImageDraw.Draw(p)
    d.rounded_rectangle([0, 0, 6, p.height - 1], 3, fill=color + (255,))
    d.text((28, 14), text, font=f1, fill=WHITE)
    if sub:
        d.text((28, 54), sub, font=f2, fill=(255, 255, 255, 170))
    p.putalpha(p.getchannel('A').point(lambda v: int(v * a)))
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    im.alpha_composite(p, (48 - int((1 - a) * 30), H - 64 - p.height))
    return im

# ---------- 字幕 ----------
def subtitle(text, a=1.0):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = F(40, 'zh')
    tw = d.textlength(text, font=f)
    y = H - 120
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            if dx * dx + dy * dy <= 9:
                d.text((W / 2 - tw / 2 + dx, y + dy), text, font=f, fill=(0, 0, 0, int(200 * a)))
    d.text((W / 2 - tw / 2, y), text, font=f, fill=(255, 255, 255, int(255 * a)))
    return im

# ---------- 挥杆数据卡（右下） ----------
def shot_card(info, t, dur):
    """info: club, ball_mph, carry, tempo, shot_no"""
    if t < 0 or t > dur:
        return None
    a = ease(t / 0.4) * (1 - ease((t - dur + 0.4) / 0.4))
    cw, ch = 400, 300
    p = panel((cw, ch), 20, 185)
    d = ImageDraw.Draw(p)
    d.text((28, 22), info['label'], font=F(18, 'sb'), fill=ACC + (255,))
    d.text((cw - 28, 22), 'EST.', font=F(15, 'sb'), fill=(255, 255, 255, 110), anchor='ra')
    d.text((26, 46), info['club'], font=F(46, 'b'), fill=WHITE)
    rows = [('BALL SPEED', f'{info["ball_mph"]}', 'MPH'), ('CARRY', f'{info["carry"]}', 'YDS'),
            ('TEMPO', info['tempo'], '')]
    for k, (lab, v, u) in enumerate(rows):
        y = 116 + k * 58
        d.line([(28, y - 6), (cw - 28, y - 6)], fill=(255, 255, 255, 30))
        d.text((28, y + 14), lab, font=F(18, 'sb'), fill=(255, 255, 255, 150))
        # 数字滚动动画
        if v.replace('.', '').isdigit() and ':' not in v:
            v = f'{int(float(v) * ease(t / 0.9))}'
        vw = d.textlength(v, font=F(40, 'b'))
        d.text((cw - 28 - (d.textlength(u, font=F(16, 'sb')) + 8 if u else 0) - vw, y), v, font=F(40, 'b'), fill=WHITE)
        if u:
            d.text((cw - 28, y + 20), u, font=F(16, 'sb'), fill=(255, 255, 255, 140), anchor='ra')
    p.putalpha(p.getchannel('A').point(lambda v: int(v * a)))
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    im.alpha_composite(p, (W - 48 - cw + int((1 - a) * 40), H - 64 - ch))
    return im

# ---------- 挥杆轨迹 + 弹道 ----------
def glow_line(size, pts, color, width, glow=10, alpha=255):
    lay = Image.new('RGBA', size, (0, 0, 0, 0))
    if len(pts) < 2:
        return lay
    g = Image.new('RGBA', size, (0, 0, 0, 0))
    ImageDraw.Draw(g).line(pts, fill=color + (int(alpha * .8),), width=width + glow, joint='curve')
    g = g.filter(ImageFilter.GaussianBlur(glow / 1.5))
    lay.alpha_composite(g)
    ImageDraw.Draw(lay).line(pts, fill=(255, 255, 255, alpha), width=max(2, width // 2), joint='curve')
    ImageDraw.Draw(lay).line(pts, fill=color + (alpha,), width=width, joint='curve')
    ImageDraw.Draw(lay).line(pts, fill=(255, 255, 255, alpha), width=max(2, width // 3), joint='curve')
    return lay

def tracer_pts(start, apex, end, frac, n=60):
    """二次贝塞尔：从 start 经 apex 到 end，取前 frac 部分"""
    out = []
    for k in range(int(n * max(0, min(1, frac))) + 1):
        u = k / n
        x = (1 - u) ** 2 * start[0] + 2 * (1 - u) * u * apex[0] + u * u * end[0]
        y = (1 - u) ** 2 * start[1] + 2 * (1 - u) * u * apex[1] + u * u * end[1]
        out.append((x, y))
    return out

# ---------- 章节标题（全屏居中） ----------
def title_frame(ov, t):
    dur = ov.get('dur', 3.5)
    if t < 0 or t > dur:
        return None
    a = ease(t / 0.5) * (1 - ease((t - dur + 0.5) / 0.5))
    im = Image.new('RGBA', (W, H), (0, 0, 0, int(110 * a)))
    d = ImageDraw.Draw(im)
    y = H // 2
    if ov.get('kicker'):
        d.text((W // 2, y - 96), ov['kicker'], font=F(26, 'sb'), fill=ACC + (int(255 * a),), anchor='mm')
    sp = int((1 - ease(t / 0.8)) * 30)
    d.text((W // 2, y - 10 + sp), ov['big'], font=F(110, 'b'), fill=(255, 255, 255, int(255 * a)), anchor='mm')
    if ov.get('small'):
        f = F(30, 'zh') if any(ord(c) > 255 for c in ov['small']) else F(30, 'sb')
        d.text((W // 2, y + 82), ov['small'], font=f, fill=(255, 255, 255, int(200 * a)), anchor='mm')
    lw = int(220 * ease(t / 0.7))
    d.rectangle([W // 2 - lw, y + 128, W // 2 + lw, y + 131], fill=ACC + (int(255 * a),))
    return im

# ---------- 常驻小地图（右上） ----------
@lru_cache(32)
def mini_map(course, hole):
    sc = SCORE[course]
    mp = Image.open(f'maps/{course}_{hole}.png').convert('RGBA')
    k = 520 / mp.height
    mp = mp.resize((int(mp.width * k), 520), Image.LANCZOS)
    cw, ch = 340, 640
    p = panel((cw, ch), 20, 180)
    d = ImageDraw.Draw(p)
    d.text((24, 20), f'{course} · HOLE {hole}', font=F(20, 'sb'), fill=ACC + (255,))
    d.text((24, 48), f'PAR {sc["par"][hole-1]}  ·  {sc["white"][hole-1]} YDS  ·  HCP {sc["hcp"][hole-1]}',
           font=F(18, 'sb'), fill=(255, 255, 255, 190))
    p.alpha_composite(mp, ((cw - mp.width) // 2, ch - mp.height - 12))
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    im.alpha_composite(p, (W - 48 - cw, 44))
    return im
