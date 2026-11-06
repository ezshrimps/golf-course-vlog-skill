"""用原声击球瞬态精修击球时刻 → downswings.json 增加 imp_a"""
import json, subprocess, numpy as np
from scipy.signal import stft
import project as P
SR = 48000
rows = json.load(open('downswings.json'))
for r in rows:
    src = P.mp4(r['clip'])
    a = r['imp'] - 0.15
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{a:.4f}', '-i', src, '-t', '0.35', '-vn', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
    x = np.frombuffer(raw, np.float32)
    f, t, Z = stft(x, SR, nperseg=256, noverlap=224)
    hf = np.abs(Z[(f > 2500)]).sum(0)
    flux = np.maximum(0, np.diff(np.log1p(hf * 50), prepend=0))
    k = int(np.argmax(flux))
    r['imp_a'] = float(a + t[k]) if flux[k] > 1.0 else r['imp']
    r['d_ms'] = round((r['imp_a'] - r['imp']) * 1000)
json.dump(rows, open('downswings.json', 'w'))
d = np.array([r['d_ms'] for r in rows])
print('offset ms median', np.median(d), 'p10/p90', np.percentile(d, [10, 90]), 'no-click', sum(1 for r in rows if r['imp_a'] == r['imp']))
