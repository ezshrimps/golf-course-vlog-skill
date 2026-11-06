"""在击球后追踪球（1920x1080 坐标）。
track(mp4, t_hit, exclude_box) -> list[(dt, x, y)]，dt 为相对击球时刻秒数"""
import subprocess, numpy as np, cv2

def frames(mp4, t0, dur, w=1920, h=1080):
    cmd = ['ffmpeg', '-v', 'error', '-hwaccel', 'cuda', '-ss', f'{t0:.3f}', '-i', mp4, '-t', f'{dur:.3f}',
           '-vf', f'scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'gray', '-']
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (w * h)
    return np.frombuffer(raw[:n * w * h], np.uint8).reshape(n, h, w)

def candidates(F, i, excl):
    a, b, c = F[i - 1].astype(np.int16), F[i].astype(np.int16), F[i + 1].astype(np.int16)
    d = np.minimum(np.abs(b - a), np.abs(b - c))
    m = (d > 22).astype(np.uint8)
    if excl is not None:
        x0, y0, x1, y1 = excl
        m[max(0, y0):y1, max(0, x0):x1] = 0
    n, lab, st, cen = cv2.connectedComponentsWithStats(m)
    out = []
    for k in range(1, n):
        if 1 <= st[k][4] <= 40 and st[k][2] <= 12 and st[k][3] <= 12:
            out.append((float(cen[k][0]), float(cen[k][1])))
    return out

def track(mp4, t_hit, excl=None, origin=None, fps=59.94, dur=3.0):
    F = frames(mp4, t_hit - 0.05, dur)
    C = [[] for _ in range(len(F))]
    for i in range(1, len(F) - 1):
        C[i] = candidates(F, i, excl)
    # 去掉在 i±2 帧同位置反复出现的闪烁点（树叶等），真球每帧都在移动
    from scipy.spatial import cKDTree
    A = [np.array(c).reshape(-1, 2) for c in C]
    T = [cKDTree(a) if len(a) else None for a in A]
    def flick(i):
        if not len(A[i]):
            return []
        bad = np.zeros(len(A[i]), bool)
        for j in (i - 2, i + 2):
            if 0 <= j < len(T) and T[j] is not None:
                dd, _ = T[j].query(A[i], distance_upper_bound=3)
                bad |= np.isfinite(dd)
        return [tuple(p) for p in A[i][~bad]]
    C = [flick(i) for i in range(len(C))]
    A = [np.array(c).reshape(-1, 2) for c in C]
    T = [cKDTree(a) if len(a) else None for a in A]
    best, best_score = [], 0
    used = set()
    # 起点：击球后 0.3s 内、（若给出）靠近球位上方的候选
    for i0 in range(1, min(len(F) - 3, int(0.35 * fps))):
        for p0 in C[i0]:
            if (i0, p0) in used:
                continue
            if origin is not None:
                if abs(p0[0] - origin[0]) > 260 or not (origin[1] - 520 < p0[1] < origin[1] + 20):
                    continue
            nb = T[i0 + 1].query_ball_point(p0, 60) if T[i0 + 1] is not None else []
            for p1 in (tuple(A[i0 + 1][k]) for k in nb):
                v = (p1[0] - p0[0], p1[1] - p0[1])
                sp = np.hypot(*v)
                if sp < 2.5 or sp > 60 or v[1] > 2:   # 刚击出的球应向上
                    continue
                trk = [(i0, *p0), (i0 + 1, *p1)]
                miss = 0
                i = i0 + 2
                while i < len(F) - 1 and miss <= 4:
                    (ia, xa, ya), (ib, xb, yb) = trk[-2], trk[-1]
                    vx, vy = (xb - xa) / (ib - ia), (yb - ya) / (ib - ia)
                    px, py = xb + vx * (i - ib), yb + vy * (i - ib)
                    tol = 4 + 1.5 * (i - ib)
                    dd, k = (T[i].query((px, py), distance_upper_bound=tol) if T[i] is not None else (np.inf, 0))
                    if np.isfinite(dd):
                        c = tuple(A[i][k])
                        trk.append((i, *c)); miss = 0
                    else:
                        miss += 1
                    i += 1
                if len(trk) >= 6:
                    used.update((ii, (xx, yy)) for ii, xx, yy in trk)
                # 按上升高度 + 长度打分（真球明显上升）
                rise = trk[0][2] - min(p[2] for p in trk)
                if len(trk) >= 8 and rise >= 60 and (not best or rise + 3 * len(trk) > best_score):
                    best, best_score = trk, rise + 3 * len(trk)
    if len(best) < 8:
        return []
    return [((i / fps) - 0.05, x, y) for i, x, y in best]

if __name__ == '__main__':
    import sys
    r = track(sys.argv[1], float(sys.argv[2]))
    print(len(r), r[:3], r[-3:])
