"""单次挥杆的 60fps 精细分析：手部轨迹、节奏、手速、球位。坐标为 1920x1080。"""
import subprocess, numpy as np
from ultralytics import YOLO

_model = None
def model():
    global _model
    if _model is None:
        _model = YOLO('yolo11m-pose.pt')
    return _model

def frames(mp4, t0, dur, w=1920, h=1080):
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{t0:.3f}', '-i', mp4, '-t', f'{dur:.3f}',
           '-vf', f'scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-']
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (w * h * 3)
    return np.frombuffer(raw[:n * w * h * 3], np.uint8).reshape(n, h, w, 3)

def analyze(mp4, t_imp, box_hint, fps=59.94, pre=2.6, post=1.6):
    """box_hint: LRF(1280x720)坐标里的人物框；返回 dict"""
    F = frames(mp4, t_imp - pre, pre + post)
    sx = 1920 / 1280
    hb = np.array(box_hint) * sx
    hc = np.array([(hb[0] + hb[2]) / 2, (hb[1] + hb[3]) / 2])
    K = []
    for s in range(0, len(F), 24):
        res = model()(list(F[s:s + 24]), verbose=False, imgsz=960, conf=0.3)
        for r in res:
            if r.keypoints is None or len(r.boxes) == 0:
                K.append(None); continue
            bx = r.boxes.xyxy.cpu().numpy()
            c = np.stack([(bx[:, 0] + bx[:, 2]) / 2, (bx[:, 1] + bx[:, 3]) / 2], 1)
            j = int(np.argmin(np.linalg.norm(c - hc, axis=1)))
            if np.linalg.norm(c[j] - hc) > (hb[3] - hb[1]):
                K.append(None); continue
            hc = 0.7 * hc + 0.3 * c[j]
            K.append(r.keypoints.data.cpu().numpy()[j])
    n = len(K)
    ts = np.arange(n) / fps - pre
    # 手部点 = 双腕中点
    hand = np.full((n, 2), np.nan)
    for i, k in enumerate(K):
        if k is not None and k[9, 2] > .3 and k[10, 2] > .3:
            hand[i] = (k[9, :2] + k[10, :2]) / 2
        elif k is not None and max(k[9, 2], k[10, 2]) > .3:
            hand[i] = k[9, :2] if k[9, 2] > k[10, 2] else k[10, :2]
    ok = ~np.isnan(hand[:, 0])
    if ok.sum() < 20:
        return None
    for d in range(2):  # 插值 + 轻度平滑
        hand[:, d] = np.interp(np.arange(n), np.where(ok)[0], hand[ok, d])
    from scipy.ndimage import uniform_filter1d
    hs = uniform_filter1d(hand, 3, axis=0)
    kk = [k for k in K if k is not None]
    sh_y = np.median([(k[5, 1] + k[6, 1]) / 2 for k in kk])
    an = np.median([(k[15, :2] + k[16, :2]) / 2 for k in kk if k[15, 2] > .3 and k[16, 2] > .3] or [[np.nan, np.nan]], axis=0)
    body_h = np.median([max(k[15, 1], k[16, 1]) - k[0, 1] for k in kk if k[0, 2] > .3 and k[15, 2] > .3] or [300])
    # 击球：t_imp 附近 ±0.25s 手最低点
    win = np.where(np.abs(ts) < 0.25)[0]
    imp = int(win[np.argmax(hs[win, 1])]) if len(win) else int(np.argmin(np.abs(ts)))
    # 上杆顶点：击球前 1.5s 内手最高点
    w2 = np.where((ts < ts[imp]) & (ts > ts[imp] - 1.5))[0]
    top = int(w2[np.argmin(hs[w2, 1])])
    # 起杆：顶点前，手离开准备位置（速度开始持续增大）
    v = np.linalg.norm(np.diff(hs, axis=0), axis=1) * fps
    # 起杆：顶点前 1.6s 内，手最后一次处在准备高度附近（离最低位 < 6% 身高）
    w0 = np.arange(max(0, top - int(1.6 * fps)), top)
    addr_y = hs[w0, 1].max() if len(w0) else hs[0, 1]
    near_addr = [i for i in w0 if hs[i, 1] > addr_y - 0.06 * body_h]
    start = near_addr[-1] if near_addr else w0[0]
    # 收杆：击球后 1.2s 内手最高点
    w3 = np.where((ts > ts[imp]) & (ts < ts[imp] + 1.3))[0]
    fin = int(w3[np.argmin(hs[w3, 1])]) if len(w3) else imp
    back = ts[top] - ts[start]; down = ts[imp] - ts[top]
    tempo = back / down if down > 0.05 else None
    # 手速（像素/秒 → 米/秒，按身高 1.75m 估比例）
    m_per_px = 1.70 / body_h
    vmax = v[top:imp + 1].max() * m_per_px if imp > top else None
    return {
        'ts': ts.tolist(), 'hand': hs.tolist(), 'start': int(start), 'top': int(top), 'imp': int(imp),
        'fin': int(fin), 'tempo': float(tempo) if tempo else None, 'back_s': float(back), 'down_s': float(down),
        'hand_mps': float(vmax) if vmax else None,
        'ankle': an.tolist(), 'body_h': float(body_h), 'sh_y': float(sh_y),
    }

if __name__ == '__main__':
    import sys, json
    r = analyze(sys.argv[1], float(sys.argv[2]), json.loads(sys.argv[3]))
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k not in ('ts', 'hand')})
