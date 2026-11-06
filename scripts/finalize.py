"""合并自动检测 + 人工修正（project.json 的 fixes）→ events.json"""
import json, numpy as np
import project as P

ev = [e for e in json.load(open('swings.json')) if not e.get('audio_only')]
F = P.CFG.get('fixes', {})
FIX = {k: [tuple(x) for x in F.get(k, [])] for k in ('partner', 'me', 'real', 'drop', 'add')}
def match(e, lst):
    return any(e['clip'] == c and abs(e['t'] - t) < 0.6 for c, t in lst)

out = []
for e in ev:
    if match(e, FIX['drop']):
        continue
    if match(e, FIX['partner']):
        e['leg'] = P.PARTNER
    if match(e, FIX['me']):
        e['leg'] = P.ME
    if match(e, FIX['real']):
        e['hit'] = e['t']
    out.append(e)

def box_at(clip, t):
    r = np.load(f'pose/{clip}.npz')['recs']
    sel = r[np.abs(r[:, 0] - t) < 0.8]
    if not len(sel):
        return None
    j = np.argmax(sel[:, 5] - sel[:, 3])   # 画面里最大的人
    return [float(v) for v in sel[j, 2:6]]

for c, t, who in FIX['add']:
    b = box_at(c, t)
    out.append({'clip': c, 't': t, 'hit': t, 'leg': P.ME if who == 'me' else P.PARTNER, 'box': b, 'manual': True,
                'h_px': (b[3] - b[1]) if b else 0})
out.sort(key=lambda e: (e['clip'], e['t']))
json.dump(out, open('events.json', 'w'), indent=0)
me_real = [e for e in out if e['leg'] == P.ME and e['hit']]
print('events', len(out), 'me real', len(me_real), 'partner real', sum(1 for e in out if e['leg'] == P.PARTNER and e['hit']),
      'me practice', sum(1 for e in out if e['leg'] == P.ME and not e['hit']))
print('no box:', [(e['clip'], e['t']) for e in out if not e.get('box')])
