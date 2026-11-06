"""从 pose + hits 找挥杆事件。输出 swings.json"""
import json, glob, os, numpy as np

def load(id_):
    z = np.load(f'pose/{id_}.npz')
    r = z['recs']
    hits = json.load(open(f'hits/{id_}.json'))['hits'] if os.path.exists(f'hits/{id_}.json') else []
    return r, float(z['fps']), hits

def tracks(r):
    """简单的逐帧最近邻跟踪，返回 {tid: [rows]}"""
    ts = np.unique(r[:, 0])
    T, last, nid = {}, {}, 0
    for t in ts:
        rows = r[r[:, 0] == t]
        used = set()
        for row in rows:
            c = np.array([(row[2] + row[4]) / 2, (row[3] + row[5]) / 2]); hgt = row[5] - row[3]
            best, bd = None, 1e9
            for tid, (lt, lc, lh) in last.items():
                if tid in used or t - lt > 1.0:
                    continue
                d = np.linalg.norm(c - lc) / max(lh, 30)
                if d < bd:
                    best, bd = tid, d
            if best is None or bd > 0.6:
                best = nid; nid += 1
            used.add(best)
            last[best] = (t, c, hgt)
            T.setdefault(best, []).append(row)
    return {k: np.array(v) for k, v in T.items() if len(v) >= 8}

def kp(row, i):
    return row[7 + i * 3: 10 + i * 3]

def hsig(row):
    """手腕相对肩的高度（以躯干长归一），上为正；None 表示不可信"""
    sh = [kp(row, 5), kp(row, 6)]; hp = [kp(row, 11), kp(row, 12)]; wr = [kp(row, 9), kp(row, 10)]
    if min(p[2] for p in sh + hp) < .3 or max(p[2] for p in wr) < .3:
        return None
    sy = (sh[0][1] + sh[1][1]) / 2; hy = (hp[0][1] + hp[1][1]) / 2
    torso = max(10, hy - sy)
    w = [p for p in wr if p[2] >= .3]
    wy = min(p[1] for p in w)  # 取更高的那只
    return (sy - wy) / torso

def legclass(rows):
    """小腿颜色：grey 长裤 / skin 短裤。HSV（OpenCV：H 0-180）"""
    th, sh = rows[:, 58:61], rows[:, 61:64]
    ok = (th[:, 0] >= 0) & (sh[:, 0] >= 0)
    if ok.sum() < 3:
        return 'unknown', None
    a, b = np.median(th[ok], 0), np.median(sh[ok], 0)
    dh = abs(a[0] - b[0]); dh = min(dh, 180 - dh)
    # 短裤：大腿（布料）与小腿（皮肤）色相差大且小腿有饱和度；长裤：两段一致
    if dh > 20 and b[1] > 40:
        return 'skin', tuple(b)
    return 'grey', tuple(b)

def find(id_):
    r, fps, hits = load(id_)
    if len(r) == 0:
        return []
    ht = [h['t'] for h in hits]
    out = []
    for tid, rows in tracks(r).items():
        t = rows[:, 0]
        hs = np.array([hsig(x) if hsig(x) is not None else np.nan for x in rows])
        hgt = np.median(rows[:, 5] - rows[:, 3])
        i = 0
        while i < len(rows):
            # 顶点：h > 0.15
            if not (hs[i] > 0.15):
                i += 1; continue
            # 向前找下降到 < -0.6（击球）再回升 > 0.0（收杆），2 秒内
            j = i + 1; imp = None
            while j < len(rows) and t[j] - t[i] < 1.2:
                if hs[j] < -0.6:
                    imp = j; break
                j += 1
            if imp is None:
                i += 1; continue
            k = imp + 1; fin = None
            while k < len(rows) and t[k] - t[imp] < 1.2:
                if hs[k] > 0.0:
                    fin = k; break
                k += 1
            if fin is None:
                i += 1; continue
            # 之前应有准备姿势（h < -0.6）在 3 秒内
            pre = [p for p in range(max(0, i - 40), i) if t[i] - t[p] < 3.5 and hs[p] < -0.6]
            if not pre:
                i = fin + 1; continue
            # 击球时刻：顶点到收杆之间 h 最低
            seg = list(range(i, fin + 1))
            m = min(seg, key=lambda q: hs[q] if not np.isnan(hs[q]) else 9)
            ti = float(t[m])
            near = [h for h in ht if -0.5 < h - ti < 0.6]
            out.append({'clip': id_, 't': ti, 'top': float(t[i]), 'fin': float(t[fin]), 'tid': int(tid),
                        'hit': float(near[0]) if near else None,
                        'box': [float(v) for v in np.median(rows[seg, 2:6], axis=0)], 'h_px': float(hgt)})
            i = fin + 1
    # 腿部分类（以该轨迹在事件前后 5s 的数据为准）
    trs = tracks(r)
    for e in out:
        rows = trs[e['tid']]
        sel = rows[(rows[:, 0] > e['t'] - 5) & (rows[:, 0] < e['t'] + 5)]
        e['leg'], e['leg_hsv'] = legclass(sel)
        if e['leg_hsv'] is not None:
            e['leg_hsv'] = [float(v) for v in e['leg_hsv']]
    # 去重：同一时刻（±1s）只留一个
    out.sort(key=lambda e: e['t'])
    ded = []
    for e in out:
        if ded and abs(e['t'] - ded[-1]['t']) < 1.0:
            if e['h_px'] > ded[-1]['h_px']:
                ded[-1] = e
            continue
        ded.append(e)
    # 没有被 pose 抓到的击球声也留下，标记为 audio_only（之后人工核对）
    for h in hits:
        if not any(abs(h['t'] - e['t']) < 1.0 for e in ded):
            ded.append({'clip': id_, 't': h['t'], 'hit': h['t'], 'audio_only': True, 'ratio': h['ratio']})
    ded.sort(key=lambda e: e['t'])
    return ded

if __name__ == '__main__':
    allv = []
    for f in sorted(glob.glob('pose/*.npz')):
        id_ = os.path.basename(f)[:4]
        ev = find(id_)
        allv += ev
        sw = [e for e in ev if not e.get('audio_only')]
        print(id_, 'swings', len(sw), 'real', sum(1 for e in sw if e['hit']),
              ' '.join(f"{e['t']:.1f}{'*' if e['hit'] else ''}{e['leg'][0]}" for e in sw))
    json.dump(allv, open('swings.json', 'w'), indent=0)
