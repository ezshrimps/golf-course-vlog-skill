"""从 OSM 渲染每洞地图（发球台在下、果岭在上）。没有 osm.json 时先从 Overpass 下载球场中心 1.5km 内的高尔夫要素。"""
import json, math, os, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import project as PJ

LAT0, LON0 = PJ.CFG['center']
if not os.path.exists('osm.json'):
    q = (f'[out:json][timeout:60];(way["golf"](around:1200,{LAT0},{LON0});relation["golf"](around:1200,{LAT0},{LON0});'
         f'way["leisure"="golf_course"](around:1500,{LAT0},{LON0}););out geom tags;')
    req = urllib.request.Request('https://overpass-api.de/api/interpreter', urllib.parse.urlencode({'data': q}).encode(),
                                 headers={'User-Agent': 'golf-course-vlog/1.0'})
    open('osm.json', 'wb').write(urllib.request.urlopen(req, timeout=90).read())
D = json.load(open('osm.json'))
def xy(p):
    return ((p['lon'] - LON0) * 111320 * math.cos(math.radians(LAT0)), (p['lat'] - LAT0) * 110540)

holes = [e for e in D['elements'] if e['tags'].get('golf') == 'hole']
# OSM 里每个九洞按顺序各 9 个 hole；用 par 序列和记分卡比对认出是哪个九洞（OSM 的 par 偶尔标错一两个）
chunks = [sorted(holes[k:k + 9], key=lambda h: int(h['tags']['ref'])) for k in range(0, len(holes), 9)]
sigs = [''.join(h['tags'].get('par', '?') for h in c) for c in chunks]
groups = {}
for name, sc in PJ.SCORE.items():
    want = ''.join(map(str, sc['par']))
    dist = [sum(a != b for a, b in zip(s, want)) for s in sigs]
    k = min(range(len(sigs)), key=dist.__getitem__)
    assert dist[k] <= 2, f'{name}: OSM 里找不到 par 序列接近 {want} 的九洞 {sigs}'
    groups[name] = chunks[k]
    print(name, sigs[k], 'vs scorecard', want)

feats = []
for e in D['elements']:
    t = e['tags'].get('golf')
    if t in ('fairway', 'green', 'bunker', 'tee', 'cartpath', 'path') and 'geometry' in e:
        feats.append((t, [xy(p) for p in e['geometry']]))
    if e['type'] == 'relation' and 'members' in e:
        for m in e['members']:
            if m.get('geometry') and t in ('fairway', 'green', 'bunker', 'tee'):
                feats.append((t, [xy(p) for p in m['geometry']]))

def seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy or 1
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)

def poly_dist(p, line):
    return min(seg_dist(p, line[i], line[i + 1]) for i in range(len(line) - 1))

COL = {'fairway': (86, 160, 92), 'green': (140, 214, 120), 'bunker': (226, 208, 160),
       'tee': (110, 190, 110), 'cartpath': (90, 96, 104), 'path': (90, 96, 104)}

def render(course, idx, W=560, H=900):
    h = groups[course][idx]
    line = [xy(p) for p in h['geometry']]
    (tx, ty), (gx, gy) = line[0], line[-1]
    ang = math.atan2(gx - tx, gy - ty)  # 旋转使 tee->green 指向上
    ca, sa = math.cos(ang), math.sin(ang)
    def rot(p):
        x, y = p[0] - tx, p[1] - ty
        return (x * ca - y * sa, x * sa + y * ca)
    rl = [rot(p) for p in line]
    length = rl[-1][1]
    xs = [p[0] for p in rl]
    span_y = length + 70
    span_x = max(140, (max(xs) - min(xs)) + 140)
    sc = min((H - 120) / span_y, (W - 60) / span_x)
    cx = (max(xs) + min(xs)) / 2
    def px(p):
        return (W / 2 + (p[0] - cx) * sc, H - 70 - (p[1] + 25) * sc)
    SS = 3
    im = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    def P(p):
        q = px(p); return (q[0] * SS, q[1] * SS)
    def cen(pts):
        return (sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts))
    near = [(t, pts) for t, pts in feats if t in ('green', 'bunker', 'fairway', 'tee') and
            poly_dist(cen(pts), line) < (28 if t != 'bunker' else 40) and
            -20 < rot(cen(pts))[1] < length + 30]
    # 合成球道走廊：rough 宽 70m，fairway 宽 32m（par3 无球道）
    def band(w, y0, y1):
        L, R = [], []
        for i in range(len(rl) - 1):
            (x0, ya), (x1, yb) = rl[i], rl[i + 1]
            n = 20
            for k in range(n + 1):
                x = x0 + (x1 - x0) * k / n; y = ya + (yb - ya) * k / n
                if y0 <= y <= y1:
                    nx, ny = -(yb - ya), (x1 - x0); nl = math.hypot(nx, ny) or 1
                    L.append(P((x + nx / nl * w / 2, y + ny / nl * w / 2)))
                    R.append(P((x - nx / nl * w / 2, y - ny / nl * w / 2)))
        return L + R[::-1]
    rough = band(70, -10, length + 25)
    d.polygon(rough, fill=(38, 74, 48, 200))
    if length > 190:
        d.polygon(band(32, 90, length - 10), fill=(72, 140, 80, 235))
    gpx = P(rl[-1]); rr = 15 * sc * SS
    d.ellipse([gpx[0] - rr, gpx[1] - rr, gpx[0] + rr, gpx[1] + rr], fill=COL['green'] + (255,))
    for layer in ('fairway', 'tee', 'bunker', 'green'):
        for t, pts in near:
            if t != layer:
                continue
            rp = [P(rot(q)) for q in pts]
            if t in ('cartpath', 'path') and pts[0] != pts[-1]:
                d.line(rp, fill=COL[t] + (200,), width=3 * SS)
            elif len(rp) > 2:
                d.polygon(rp, fill=COL[t] + (235,))
    # 中线（虚线）+ 码数刻度
    pl = [P(p) for p in rl]
    for i in range(len(pl) - 1):
        (x0, y0), (x1, y1) = pl[i], pl[i + 1]
        n = int(math.hypot(x1 - x0, y1 - y0) / (14 * SS))
        for k in range(0, n, 2):
            a, b = k / n, (k + 1) / n
            d.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)],
                   fill=(255, 255, 255, 220), width=2 * SS)
    # 发球台与旗杆
    tp, gp = pl[0], pl[-1]
    r = 9 * SS
    d.ellipse([tp[0] - r, tp[1] - r, tp[0] + r, tp[1] + r], fill=(255, 255, 255, 255))
    d.ellipse([tp[0] - r / 2, tp[1] - r / 2, tp[0] + r / 2, tp[1] + r / 2], fill=(20, 24, 28, 255))
    d.line([gp, (gp[0], gp[1] - 34 * SS)], fill=(255, 255, 255, 255), width=3 * SS)
    d.polygon([(gp[0], gp[1] - 34 * SS), (gp[0] + 20 * SS, gp[1] - 28 * SS), (gp[0], gp[1] - 22 * SS)],
              fill=(255, 196, 0, 255))
    # 码数刻度 100/150/200/250
    f = ImageFont.truetype(PJ.FONTS + 'bahnschrift.ttf', 15 * SS)
    for yd in (100, 150, 200, 250, 300):
        m = yd * 0.9144
        if m > length - 25:
            break
        y = P((0, m))[1]
        d.line([(P((cx, m))[0] - 70 * SS, y), (P((cx, m))[0] - 50 * SS, y)], fill=(255, 255, 255, 150), width=2 * SS)
        d.text((P((cx, m))[0] - 112 * SS, y - 9 * SS), f'{yd}', font=f, fill=(255, 255, 255, 170))
    im = im.resize((W, H), Image.LANCZOS)
    meta = {'length_m': length, 'tee_px': px(rl[0]), 'green_px': px(rl[-1]),
            'path_px': [px(p) for p in rl], 'scale': sc}
    return im, meta

if __name__ == '__main__':
    import os
    os.makedirs('maps', exist_ok=True)
    allmeta = {}
    for c in PJ.SCORE:
        for i in range(9):
            im, meta = render(c, i)
            im.save(f'maps/{c}_{i + 1}.png')
            allmeta[f'{c}_{i + 1}'] = meta
    json.dump(allmeta, open('maps/meta.json', 'w'))
    print('ok')
