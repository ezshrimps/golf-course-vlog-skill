"""按 edl.json 渲染 vlog：ffmpeg 解码裁剪 → PIL 叠加 UI → NVENC 编码。
用法: python render.py edl.json out.mp4 [start_idx end_idx]"""
import sys, json, subprocess, math, numpy as np
from PIL import Image
import ui
import project as P

W, H, FPS = 1920, 1080, 60000 / 1001

def src(clip):
    return P.mp4(clip)

def decode(seg):
    """返回逐帧 RGB ndarray 的生成器；zoom: [cx, cy, s] 以 4K 坐标为准"""
    a, b = seg['in'], seg['out']
    z = seg.get('zoom')
    rot = seg.get('rotate')
    vf = []
    if rot == 180:
        vf.append('hflip,vflip')
    if z:
        cx, cy, s = z
        cw, ch = 3840 / s, 2160 / s
        x0 = min(max(0, cx - cw / 2), 3840 - cw); y0 = min(max(0, cy - ch / 2), 2160 - ch)
        vf.append(f'crop={int(cw)//2*2}:{int(ch)//2*2}:{int(x0)}:{int(y0)}')
    vf.append(f'scale={W}:{H}:flags=lanczos')
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{a:.3f}', '-i', src(seg['clip']), '-t', f'{b - a:.3f}',
           '-vf', ','.join(vf), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=W * H * 3 * 4)
    n = 0
    while True:
        buf = p.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        yield np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        n += 1
    p.wait()

def to_view(seg, x, y):
    """原始 1920x1080 全幅坐标 → 当前裁剪视图坐标"""
    z = seg.get('zoom')
    if not z:
        return x, y
    cx, cy, s = z
    cw, ch = 3840 / s, 2160 / s
    x0 = min(max(0, cx - cw / 2), 3840 - cw); y0 = min(max(0, cy - ch / 2), 2160 - ch)
    return (x * 2 - x0) * s / 2, (y * 2 - y0) * s / 2

def comp(frame, layer):
    """把 RGBA 叠加层合成到帧上（只处理非透明包围盒）"""
    if layer is None:
        return frame
    bb = layer.getbbox()
    if not bb:
        return frame
    x0, y0, x1, y1 = bb
    L = np.asarray(layer.crop(bb), np.float32)
    a = L[:, :, 3:4] / 255
    f = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = (f * (1 - a) + L[:, :, :3] * a).astype(np.uint8)
    return frame

def flight(seg, tr):
    """在当前视图坐标里生成球路 [(dt, x, y)]。有真实追踪就用追踪点，之后按透视飞行补全到落点。"""
    s = (seg.get('zoom') or [0, 0, 1])[2]
    bx, by = to_view(seg, *tr['ball'])
    horizon = H * 0.40
    apex_rel = {'driver': 0.80, 'hybrid': 0.72, 'iron': 0.66}[tr['kind']]
    side = tr.get('side', 0)
    land_x = bx + side * W * 0.07 + W * 0.02
    land_y = horizon + 12
    T_END = 3.0
    dx = (side if side else 0.45) * W * {'driver': 0.22, 'hybrid': 0.18, 'iron': 0.15}[tr['kind']]
    land_x = bx + dx
    apex_y = max(90, horizon - apex_rel * (horizon - 90))
    def pred(t0, x0, y0):
        # 三次贝塞尔：先近乎竖直升起，再侧向画弧落到地平线
        P = [(x0, y0), (x0 + dx * 0.05, apex_y - 0.25 * (y0 - apex_y)), (x0 + dx * 0.85, apex_y - 30), (land_x, land_y)]
        out = []
        for k in range(1, 200):
            t = t0 + k / 30
            if t > T_END:
                break
            u = (t - t0) / (T_END - t0)
            e = 1 - (1 - u) ** 2.2                      # 越远越慢（透视）
            a, b, c, d = (1 - e) ** 3, 3 * (1 - e) ** 2 * e, 3 * (1 - e) * e * e, e ** 3
            out.append((t, a * P[0][0] + b * P[1][0] + c * P[2][0] + d * P[3][0],
                        a * P[0][1] + b * P[1][1] + c * P[2][1] + d * P[3][1]))
        return out
    track = tr.get('track') or []
    if len(track) >= 8:
        pts = [(dt, *to_view(seg, x, y)) for dt, x, y in track if dt >= 0]
        pts = [p for p in pts if -50 < p[2] < H + 50]
        if len(pts) >= 6:
            t0, x0, y0 = pts[-1]
            if y0 > 30 and t0 < T_END - 0.3:   # 还在画面里就丢失了：沿当前速度方向弯向落点
                ta, xa, ya = pts[max(0, len(pts) - 5)]
                vx, vy = (x0 - xa) / max(1e-3, t0 - ta), (y0 - ya) / max(1e-3, t0 - ta)
                cx, cy = x0 + vx * 0.6, min(y0 + vy * 0.6, y0)
                for k in range(1, 200):
                    t = t0 + k / 30
                    if t > T_END:
                        break
                    u = 1 - (1 - (t - t0) / (T_END - t0)) ** 1.5
                    x = (1 - u) ** 2 * x0 + 2 * (1 - u) * u * cx + u * u * land_x
                    y = (1 - u) ** 2 * y0 + 2 * (1 - u) * u * cy + u * u * land_y
                    pts.append((t, x, y))
            return pts, len(track)
    return [(0.0, bx, by)] + pred(0.0, bx, by), 0

def swing_layers(seg, ov, t):
    """挥杆叠加：手部轨迹（逐帧生长）+ 球路（追踪 + 预测）+ 数据卡"""
    d = ov['data']
    out = []
    ti = ov['t_imp']                      # 段内击球时刻
    rel = t - ti
    hand = d.get('hand'); ts = d.get('ts')
    if hand and ov.get('show_path', True):
        st, top, imp, fin = d['start'], d['top'], d['imp'], d['fin']
        cur = int(round((rel - ts[0]) * FPS))  # 当前在 hand 数组中的下标
        fade = 1.0 if rel < 2.2 else max(0, 1 - (rel - 2.2) / 0.6)
        if cur > st and fade > 0:
            pts = [to_view(seg, *hand[k]) for k in range(st, min(cur, fin) + 1)]
            nb = max(0, min(cur, top) - st + 1)
            if nb >= 2:
                out.append(ui.glow_line((W, H), pts[:nb], (255, 255, 255), 5, 10, int(210 * fade)))
            if len(pts) - nb + 1 >= 2:
                out.append(ui.glow_line((W, H), pts[max(0, nb - 1):], ui.ACC, 7, 14, int(255 * fade)))
    # 球路
    tr = ov.get('tracer')
    if tr and rel > 0:
        if 'pts' not in tr:
            tr['pts'], tr['tracked'] = flight(seg, tr)
        fade = 1.0 if rel < ov.get('tracer_hold', 3.2) else max(0, 1 - (rel - ov.get('tracer_hold', 3.2)) / 0.6)
        pts = [(x, y) for (dt, x, y) in tr['pts'] if dt <= rel]
        if len(pts) >= 2 and fade > 0:
            out.append(ui.glow_line((W, H), pts, (255, 92, 64), 6, 14, int(255 * fade)))
            if rel > 0.6:
                lab = 'BALL TRACKED' if tr.get('tracked') else 'PREDICTED FLIGHT'
                x, y = pts[-1]
                x = min(max(x + 18, 20), W - 240); y = min(max(y - 14, 20), H - 40)
                L = Image.new('RGBA', (W, H), (0, 0, 0, 0))
                d = ui.ImageDraw.Draw(L)
                a = int(220 * fade * min(1, (rel - 0.6) / 0.3))
                tw = d.textlength(lab, font=ui.F(16, 'sb'))
                d.rounded_rectangle([x, y, x + tw + 20, y + 28], 8, fill=(12, 16, 20, int(a * 0.7)))
                d.text((x + 10, y + 5), lab, font=ui.F(16, 'sb'), fill=(255, 140, 110, a))
                out.append(L)
    card = ov.get('card')
    if card:
        c = ui.shot_card(card, rel - 0.5, ov.get('card_dur', 3.4))
        if c is not None:
            out.append(c)
    return out

def render(edl, out, rng=None):
    segs = edl['segments']
    if rng:
        segs = segs[rng[0]:rng[1]]
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                            '-r', '60000/1001', '-i', '-', '-c:v', 'h264_nvenc', '-preset', 'p5', '-rc', 'vbr',
                            '-cq', '19', '-b:v', '24M', '-maxrate', '40M', '-pix_fmt', 'yuv420p', out],
                           stdin=subprocess.PIPE)
    total = 0
    for si, seg in enumerate(segs):
        dur = seg['out'] - seg['in']
        hud_key = seg.get('hole')
        nfr = int(round(dur * FPS))
        def exact(gen):
            last, k = None, -1
            for k, f in enumerate(gen):
                if k >= nfr:
                    break
                last = f
                yield f
            else:
                k += 1
                if last is None:
                    last = np.zeros((H, W, 3), np.uint8)
                while k < nfr:
                    yield last; k += 1
        for n, fr in enumerate(exact(decode(seg))):
            t = n / FPS
            fr = fr.copy()
            # 片段边缘淡入淡出（4 帧）
            e = min(n, int(dur * FPS) - n)
            if e < 4 and seg.get('fade', True):
                fr = (fr * ((e + 1) / 5)).astype(np.uint8)
            layers = []
            if hud_key and not seg.get('no_hud'):
                layers.append(ui.hud(hud_key[0], hud_key[1], seg.get('clock', '')))
            for ov in seg.get('overlays', []):
                k = ov['type']
                if k == 'holecard':
                    layers.append(ui.hole_card_frame(hud_key[0], hud_key[1], t - ov.get('at', 0), ov.get('dur', 5.5)))
                elif k == 'tag':
                    layers.append(ui.tag_frame(ov['text'], ov.get('sub', ''), t - ov.get('at', 0), ov.get('dur', 3),
                                               tuple(ov['color']) if 'color' in ov else ui.ACC))
                elif k == 'sub':
                    if ov['at'] <= t <= ov['at'] + ov['dur']:
                        a = min(1, (t - ov['at']) / 0.15, (ov['at'] + ov['dur'] - t) / 0.15)
                        layers.append(ui.subtitle(ov['text'], a))
                elif k == 'swing':
                    layers += swing_layers(seg, ov, t)
                elif k == 'minimap':
                    layers.append(ui.mini_map(hud_key[0], hud_key[1]))
                elif k == 'title':
                    layers.append(ui.title_frame(ov, t - ov.get('at', 0)))
            for L in layers:
                fr = comp(fr, L)
            enc.stdin.write(fr.tobytes())
            total += 1
        print(f'seg {si} {seg["clip"]} {seg["in"]:.1f}-{seg["out"]:.1f} done, frames {total}', flush=True)
    enc.stdin.close(); enc.wait()

if __name__ == '__main__':
    edl = json.load(open(sys.argv[1], encoding='utf-8'))
    rng = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else None
    render(edl, sys.argv[2], rng)
