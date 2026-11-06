"""events.json + shots/ + edl_cfg.json → edl.json（整场 vlog 的剪辑表）"""
import json, os, math
import numpy as np
import project as P
from project import SCORE, TEES
from trackcheck import good_track

cfg = json.load(open('edl_cfg.json', encoding='utf-8'))

def hole_of(clip):
    h = None
    for c, course, n in TEES:
        if clip >= c:
            h = (course, n)
    return h

clock = P.clock

ev = json.load(open('events.json'))
drop = {(d[0], d[1]) for d in cfg.get('drop', [])}
force_real = {(d[0], d[1]) for d in cfg.get('force_real', [])}
def key(e):
    return (e['clip'], round(e['t'], 1))
for e in ev:
    if key(e) in force_real:
        e['hit'] = e['t']

def is_dropped(e):
    return any(e['clip'] == c and abs(e['t'] - t) < 0.6 for c, t in drop)

def zoom_for(box, target=0.5, smax=1.9):
    x0, y0, x1, y1 = box
    h = y1 - y0
    s = max(1.0, min(smax, target * 720 / max(h, 1)))
    cx = (x0 + x1) / 2 * 3
    cy = (y0 + y1) / 2 * 3 - 0.06 * 2160 / s   # 人物略偏下，给球路留天空
    return [cx, cy, s]

# ---- 用杆 / 球速估算 ----
def club_for(course, hole, is_tee, remaining, bunker=False):
    par = SCORE[course]['par'][hole - 1]
    if bunker:
        return 'SAND WEDGE', 'wedge', 'BUNKER SHOT'
    if is_tee and par >= 4:
        return 'DRIVER', 'driver', 'TEE SHOT'
    label = 'TEE SHOT' if is_tee else ('FAIRWAY' if remaining > 120 else 'APPROACH' if remaining > 35 else 'CHIP')
    if remaining <= 35:
        return 'LOB WEDGE', 'wedge', label
    for lim, name, k in [(205, '3 HYBRID', 'hybrid'), (180, '5 IRON', 'iron'), (162, '6 IRON', 'iron'),
                         (148, '7 IRON', 'iron'), (134, '8 IRON', 'iron'), (120, '9 IRON', 'iron'),
                         (100, 'PITCHING WEDGE', 'wedge'), (70, 'GAP WEDGE', 'wedge')]:
        if remaining >= lim:
            return name, k, label
    return 'SAND WEDGE', 'wedge', label

LEVER = {'driver': 4.2, 'hybrid': 4.1, 'iron': 3.9, 'wedge': 3.6}
SMASH = {'driver': 1.44, 'hybrid': 1.38, 'iron': 1.32, 'wedge': 1.20}
CARRY = {'driver': 1.62, 'hybrid': 1.45, 'iron': 1.33, 'wedge': 1.10}
CLAMP = {'driver': (105, 150), 'hybrid': (95, 135), 'iron': (82, 125), 'wedge': (20, 100)}

def numbers(kind, hand_mps, remaining):
    ch = (hand_mps or 8.5) * LEVER[kind] * 2.237
    bs = ch * SMASH[kind]
    lo, hi = CLAMP[kind]
    bs = max(lo, min(hi, bs))
    carry = bs * CARRY[kind]
    if kind == 'wedge' and carry > remaining * 1.05:
        carry = remaining * 1.05
        bs = carry / CARRY[kind]          # 球速与飞行距离保持一致
    return int(round(bs)), int(round(carry))

def tracer_pts(track, detail, seg_zoom, kind):
    """真实追踪 + 物理外推；无追踪则按机位合成预测弹道。返回 [(dt,x,y)]（1920 全幅坐标）"""
    pts = []
    if track and len(track) >= 8:
        T = np.array(track)
        dt, x, y = T[:, 0], T[:, 1], T[:, 2]
        px = np.polyfit(dt, x, 1); py = np.polyfit(dt, y, 2)
        pts = [tuple(p) for p in T]
        t = dt[-1]
        while t < 3.2:
            t += 1 / 30
            yy = np.polyval(py, t); xx = np.polyval(px, t)
            if yy > y[0] + 20 or yy < -400:
                break
            pts.append((t, xx, yy))
        return pts, len(track)
    if not detail or kind == 'wedge':
        return [], 0
    ax, ay = detail['ankle']
    if ax != ax:
        return [], 0
    bh = detail['body_h']
    x0, y0 = ax + 0.05 * bh, ay
    # 背后机位：球飞向远处——先快速上升，再在远处落下
    apex_h = {'driver': 2.4, 'hybrid': 2.6, 'iron': 2.7}[kind] * bh
    drift = 0.25 * bh
    for k in range(0, 91):
        t = k / 30
        u = 1 - math.exp(-t / 0.9)            # 透视收缩
        yy = y0 - apex_h * (4 * u * (1 - u)) * 1.0 - u * 0.6 * bh
        xx = x0 + drift * u
        pts.append((t, xx, yy))
    return pts, 0

segments = []
def add(seg):
    segments.append(seg)

# 片头
for t in cfg['intro']:
    add(t)

holes_done = set()
shot_counter = {}
remaining = {}
for c, course, n in TEES:
    pass

by_hole = {}
for e in sorted(ev, key=lambda e: (e['clip'], e['t'])):
    if is_dropped(e):
        continue
    h = hole_of(e['clip'])
    by_hole.setdefault(h, []).append(e)

extras = cfg.get('extras', [])  # 开车 / 果岭 / 对话 等手选片段
for course, n in [(c, k) for _, c, k in TEES]:
    h = (course, n)
    evs = by_hole.get(h, [])
    real = [e for e in evs if e['hit']]
    prac = [e for e in evs if not e['hit'] and e['leg'] == P.ME and e.get('full', True)]
    yards = SCORE[course]['white'][n - 1]
    remaining[h] = yards
    ct = cfg['course_titles'].get(course)   # 每个九洞开头的章节标题
    if ct and n == 1:
        add({'clip': ct['clip'], 'in': ct['in'], 'out': ct['in'] + 3.6, 'no_hud': True,
             'overlays': [{'type': 'title', 'kicker': ct['kicker'], 'big': ct['big'], 'small': ct['small'], 'dur': 3.6}]})
    # 选一次空挥：第一记真挥杆前最近的一次你的空挥
    pick_prac = []
    if prac:
        pick_prac = [prac[0]]
    items = []
    for e in real:
        items.append(('real', e))
    for e in pick_prac:
        items.append(('prac', e))
    for x in extras:
        if tuple(x['hole']) == h:
            items.append(('extra', x))
    def tkey(it):
        k, e = it
        return (e['clip'], e['t'] if k != 'extra' else e['in'])
    items.sort(key=tkey)
    first = True
    sc = 0
    for k, e in items:
        if k == 'extra':
            seg = dict(e); seg['hole'] = list(h); seg['clock'] = clock(e['clip'], e['in'])
            seg.setdefault('overlays', [])
            add(seg); continue
        me = e['leg'] == P.ME
        t = e['t']
        if k == 'prac':
            seg = {'clip': e['clip'], 'in': t - 2.0, 'out': t + 1.5, 'hole': list(h), 'clock': clock(e['clip'], t),
                   'zoom': zoom_for(e['box']),
                   'overlays': [{'type': 'tag', 'text': 'PRACTICE SWING', 'sub': '空挥找感觉', 'at': 0.4, 'dur': 2.8,
                                 'color': [255, 255, 255]}]}
            add(seg); continue
        pre = 7.6 if first else (2.8 if me else 2.3)
        post = 3.8 if me else 2.6
        seg = {'clip': e['clip'], 'in': max(0, t - pre), 'out': t + post, 'hole': list(h),
               'clock': clock(e['clip'], t), 'overlays': []}
        if first:
            seg['overlays'].append({'type': 'holecard', 'at': 0, 'dur': 5.4})
        else:
            seg['zoom'] = zoom_for(e['box'])
        if me:
            sc += 1
            f = f'shots/{e["clip"]}_{e["t"]:.2f}.json'
            S = json.load(open(f)) if os.path.exists(f) else {}
            d = S.get('detail')
            bunker = (e['clip'], round(t, 1)) in {(b[0], b[1]) for b in cfg.get('bunker', [])}
            tee_clip = next(c for c, cc, nn in TEES if (cc, nn) == h)
            is_tee = e['clip'] == tee_clip
            if is_tee:
                remaining[h] = yards            # 发球台上多打的球（mulligan）各自从洞长重新算
            hand = d['hand_mps'] if d else None
            if is_tee or bunker:
                club, kind, label = club_for(course, n, is_tee, remaining[h], bunker)
            elif (hand or 0) >= 6.5:
                club, kind, label = 'IRON', 'iron', 'FAIRWAY'
            elif (hand or 0) >= 4.5:
                club, kind, label = 'WEDGE', 'wedge', 'PITCH'
            else:
                club, kind, label = 'WEDGE', 'wedge', 'CHIP'
            if not is_tee:
                remaining[h] = 999
            bs, carry = numbers(kind, hand, remaining[h])
            remaining[h] = max(15, remaining[h] - int(carry * 1.08))
            t_imp = S.get('t_imp', t)
            ov = {'type': 'swing', 't_imp': t_imp - seg['in'], 'data': d or {},
                  'card': {'label': label, 'club': club, 'ball_mph': bs, 'carry': carry,
                           'tempo': f'{d["tempo"]:.1f} : 1' if d and d.get('tempo') and 1.5 < d['tempo'] < 5.5 else '—'}}
            # 第一杆（有球洞卡）时数据卡与球洞卡错开：卡片 5.4s 后才出现
            if kind != 'wedge' and d and d['ankle'][0] == d['ankle'][0]:
                ov['tracer'] = {'track': S.get('track') if good_track(S.get('track'), d['ankle']) else [], 'ball': d['ankle'], 'body_h': d['body_h'],
                                'kind': kind, 'side': (sc % 3) - 1}
            if d:
                # hand/ts 以 e['t'] 为零点 → 转为相对 t_imp 的时间
                off = e['t'] - t_imp
                d2 = dict(d); d2['ts'] = [x + off for x in d['ts']]
                ov['data'] = d2
            seg['overlays'].append(ov)
        else:
            seg['overlays'].append({'type': 'tag', 'text': 'PARTNER', 'sub': '球友', 'at': 0.3, 'dur': 2.2,
                                    'color': [120, 190, 255]})
        add(seg)
        first = False

for t in cfg['outro']:
    add(t)

# 合并同一片段中重叠的段
merged = []
for s in segments:
    if merged and s['clip'] == merged[-1]['clip'] and s['in'] < merged[-1]['out'] + 0.3 \
            and s.get('zoom') == merged[-1].get('zoom') and s.get('hole') == merged[-1].get('hole'):
        m = merged[-1]
        shift = s['in'] - m['in']
        for ov in s['overlays']:
            ov = dict(ov)
            for k in ('at', 't_imp'):
                if k in ov:
                    ov[k] += shift
            m['overlays'].append(ov)
        m['out'] = max(m['out'], s['out'])
    elif merged and s['clip'] == merged[-1]['clip'] and s['in'] < merged[-1]['out']:
        # 不同构图的重叠：前段截短到后段开始
        merged[-1]['out'] = s['in']
        merged.append(s)
    else:
        merged.append(s)
tot = sum(s['out'] - s['in'] for s in merged)
json.dump({'segments': merged}, open('edl.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(len(merged), 'segments', f'{tot/60:.1f} min')
