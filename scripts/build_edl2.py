"""精简版：你的满意球 / 球友全部出杆。用法: python build_edl2.py me|partner"""
import sys, json, os
import build_edl as B   # 复用球洞、时钟、用杆与球速估算（导入会顺带生成一次 edl.json，无副作用）
import project as P
from project import SCORE

who = sys.argv[1]
cfg = json.load(open('edl_cfg.json', encoding='utf-8'))['highlights']
KICKER = f"{P.LABEL} · {P.start(P.clips()[0]):%Y.%m.%d}"
THRESH = cfg.get('hold_sec', 2.0)   # 收杆停留超过这个秒数算满意球
ev = json.load(open('events.json'))
if who == 'me':
    hold = {(h['clip'], round(h['t'], 2)): h for h in json.load(open('hold.json'))}
    sel = [e for e in ev if e['leg'] == P.ME and e['hit'] and hold[(e['clip'], round(e['t'], 2))]['hold'] >= THRESH]
    shot_dir = 'shots'
    intro = {'clip': cfg['intro_me']['clip'], 'in': cfg['intro_me']['in'], 'out': cfg['intro_me']['in'] + 3.6, 'no_hud': True,
             'overlays': [{'type': 'title', 'kicker': KICKER, 'big': 'BEST SHOTS',
                           'small': f'收杆停得住的 {len(sel)} 球', 'dur': 3.6}]}
else:
    sel = [e for e in ev if e['leg'] == P.PARTNER and e['hit']]
    shot_dir = 'shots_p'
    intro = {'clip': cfg['intro_partner']['clip'], 'in': cfg['intro_partner']['in'], 'out': cfg['intro_partner']['in'] + 3.6, 'no_hud': True,
             'overlays': [{'type': 'title', 'kicker': KICKER, 'big': 'PARTNER CAM',
                           'small': f'球友的全部 {len(sel)} 杆', 'dur': 3.6}]}

segs = [intro]
for e in sorted(sel, key=lambda e: (e['clip'], e['t'])):
    h = B.hole_of(e['clip'])
    course, n = h
    f = f'{shot_dir}/{e["clip"]}_{e["t"]:.2f}.json'
    S = json.load(open(f)) if os.path.exists(f) else {}
    d = S.get('detail')
    ti = S.get('t_imp', e['t'])
    tail = 3.4
    if who == 'me':
        tail = min(4.8, max(3.4, hold[(e['clip'], round(e['t'], 2))]['hold'] + 1.4))
    tee_clip = next(c for c, cc, nn in B.TEES if (cc, nn) == h)
    is_tee = e['clip'] == tee_clip
    hand = d['hand_mps'] if d else None
    bunker = (e['clip'], round(e['t'], 1)) in {(b[0], b[1]) for b in B.cfg.get('bunker', [])}
    if is_tee or bunker:
        club, kind, label = B.club_for(course, n, is_tee, SCORE[course]['white'][n - 1], bunker)
    elif (hand or 0) >= 6.5:
        club, kind, label = 'IRON', 'iron', 'FAIRWAY'
    elif (hand or 0) >= 4.5:
        club, kind, label = 'WEDGE', 'wedge', 'PITCH'
    else:
        club, kind, label = 'WEDGE', 'wedge', 'CHIP'
    if who == 'me':
        bs, carry = B.numbers(kind, hand, SCORE[course]['white'][n - 1] if is_tee else 999)
    else:
        # 软下限：低于常见区间的部分按比例压缩，保留每杆差异
        raw = (hand or 7.0) * B.LEVER[kind] * 2.237 * B.SMASH[kind]
        lo, hi = B.CLAMP[kind]
        bs = lo - (lo - raw) * 0.35 if raw < lo else min(hi, raw)
        carry = bs * B.CARRY[kind]
        bs, carry = int(round(bs)), int(round(carry))
    tlo = 1.5 if who == 'me' else 1.1
    tempo = f'{d["tempo"]:.1f} : 1' if d and d.get('tempo') and tlo < d['tempo'] < 5.5 else '—'
    seg = {'clip': e['clip'], 'in': ti - 2.4, 'out': ti + tail, 'hole': [course, n],
           'clock': B.clock(e['clip'], ti), 'zoom': B.zoom_for(e['box'], target=0.55),
           'overlays': [{'type': 'minimap'},
                        {'type': 'swing', 't_imp': 2.4, 'data': {}, 'show_path': False,
                         'card': {'label': label, 'club': club, 'ball_mph': bs, 'carry': carry, 'tempo': tempo},
                         'card_dur': tail - 0.5}]}
    segs.append(seg)
tot = sum(s['out'] - s['in'] for s in segs)
json.dump({'segments': segs}, open(f'edl_{who}.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(who, len(segs) - 1, 'shots', f'{tot / 60:.1f} min')
