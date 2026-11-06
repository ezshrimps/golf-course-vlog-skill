"""对选定挥杆跑 60fps 精细分析 + 球追踪，结果存 <outdir>/{clip}_{t}.json。
用法: python shots.py sel.json [outdir=shots] [--no-track]"""
import sys, json, os
import swing_detail as sd, balltrack as bt

import project as P

sel = json.load(open(sys.argv[1]))
D = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else 'shots'
TRACK = '--no-track' not in sys.argv
os.makedirs(D, exist_ok=True)
for e in sel:
    out = f'{D}/{e["clip"]}_{e["t"]:.2f}.json'
    if os.path.exists(out):
        continue
    mp4 = P.mp4(e['clip'])
    ti = e.get('hit') or e['t']
    # 视频里击球时刻：用 pose 的手最低点更准；音频略有延迟
    r = sd.analyze(mp4, e['t'], e['box'])
    res = {'ev': e, 'detail': r, 'track': []}
    if r:
        t_imp = e['t'] + r['ts'][r['imp']]
        res['t_imp'] = t_imp
        if TRACK and e.get('track', True):
            bx = [v * 1.5 for v in e['box']]
            pad = (bx[3] - bx[1]) * 0.15
            excl = (int(bx[0] - pad), int(bx[1] - pad), int(bx[2] + pad), int(bx[3] + pad))
            org = r['ankle'] if r['ankle'][0] == r['ankle'][0] else ((bx[0] + bx[2]) / 2, bx[3])
            try:
                res['track'] = [list(map(float, p)) for p in bt.track(mp4, t_imp, excl=excl, origin=org)]
            except Exception as ex:
                res['err'] = str(ex)
    json.dump(res, open(out, 'w'))
    print(out, 'tempo', r and r['tempo'] and round(r['tempo'], 2), 'hand', r and r['hand_mps'] and round(r['hand_mps'], 1),
          'track', len(res['track']), flush=True)
