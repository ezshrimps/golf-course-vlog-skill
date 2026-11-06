"""每杆的上杆顶点和击球时刻（来自 shots/ 的 60fps 分析）→ downswings.json，供快剪和卡点用。"""
import json, numpy as np
import project as P

ev = [e for e in json.load(open('events.json')) if e['leg'] == P.ME and e['hit']]
rows = []
for e in ev:
    d = json.load(open(f'shots/{e["clip"]}_{e["t"]:.2f}.json'))['detail']
    if not d:
        continue
    top = e['t'] + d['ts'][d['top']]; imp = e['t'] + d['ts'][d['imp']]
    rows.append({'clip': e['clip'], 'top': top, 'imp': imp, 'down': imp - top, 'box': e['box']})
json.dump(rows, open('downswings.json', 'w'))
dn = np.array([r['down'] for r in rows])
print(len(rows), 'down swing s: median', np.median(dn), 'bad(<0.1 or >0.6):', ((dn < 0.1) | (dn > 0.6)).sum())
