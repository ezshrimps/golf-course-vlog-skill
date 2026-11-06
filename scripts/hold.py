"""测量收杆停留时长：击球后双手保持在肩以上（且身体基本不动）的连续时间。"""
import json, numpy as np
import swings as S
import project as P

ev = [e for e in json.load(open('events.json')) if e['leg'] == P.ME and e['hit']]
cache = {}
out = []
for e in ev:
    if e['clip'] not in cache:
        r, _, _ = S.load(e['clip'])
        cache[e['clip']] = r
    r = cache[e['clip']]
    sh = json.load(open(f'shots/{e["clip"]}_{e["t"]:.2f}.json'))
    ti = sh.get('t_imp', e['t'])
    bx = np.array(e['box']); bc = np.array([(bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2]); bh = bx[3] - bx[1]
    ts = np.unique(r[(r[:, 0] > ti) & (r[:, 0] < ti + 8), 0])
    series = []
    c = bc.copy()
    for t in ts:
        rows = r[r[:, 0] == t]
        cs = np.stack([(rows[:, 2] + rows[:, 4]) / 2, (rows[:, 3] + rows[:, 5]) / 2], 1)
        j = int(np.argmin(np.linalg.norm(cs - c, axis=1)))
        if np.linalg.norm(cs[j] - c) > bh * 0.8:
            series.append((t, None, None)); continue
        c = 0.7 * c + 0.3 * cs[j]
        series.append((t, S.hsig(rows[j]), cs[j]))
    # 收杆：击球后 1.2s 内首次 h>0；之后连续保持 h>-0.1 的时长
    hold, start = 0.0, None
    miss = 0
    for t, h, cc in series:
        if start is None:
            if h is not None and h > 0 and t - ti < 1.3:
                start, last, pos0 = t, t, cc
            continue
        if h is None:
            miss += 1
            if miss > 3:
                break
            continue
        miss = 0
        if h > -0.1 and np.linalg.norm(cc - pos0) < bh * 0.35:
            last = t
        else:
            break
    if start is not None:
        hold = last - start
    out.append({'clip': e['clip'], 't': e['t'], 't_imp': ti, 'hold': round(float(hold), 2)})
json.dump(out, open('hold.json', 'w'), indent=0)
h = np.array([o['hold'] for o in out])
print(len(h), 'percentiles 25/50/75/90:', np.percentile(h, [25, 50, 75, 90]))
for th in (1.0, 1.5, 2.0, 2.5):
    print(th, (h >= th).sum())
