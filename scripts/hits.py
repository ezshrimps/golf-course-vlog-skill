"""检测击球声（高频瞬态），输出 hits/<clip>.json。用法: python hits.py（全部片段）或 python hits.py in.mp4 out.json"""
import sys, json, subprocess, numpy as np
from scipy.signal import stft, find_peaks

def detect(src, out):
    SR = 32000
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-vn', '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'],
                         capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    f, t, Z = stft(x, SR, nperseg=512, noverlap=384)
    M = np.abs(Z)
    hf = M[(f > 2500) & (f < 12000)].sum(0)
    lf = M[(f > 100) & (f < 1500)].sum(0)
    flux = np.maximum(0, np.diff(np.log1p(hf * 50), prepend=0))
    # 相对于局部（2s）中位数的突增
    w = int(2 / (t[1] - t[0]))
    med = np.array([np.median(hf[max(0, i - w):i + w]) for i in range(0, len(hf))]) if len(hf) < 40000 else None
    if med is None:
        from scipy.ndimage import median_filter
        med = median_filter(hf, size=2 * w + 1)
    ratio = hf / (med + 1e-6)
    pk, pr = find_peaks(flux, height=0.8, distance=int(0.5 / (t[1] - t[0])))
    ev = []
    for p in pk:
        r = float(ratio[p:p + 3].max())
        if r > 6:
            ev.append({'t': float(t[p]), 'flux': float(flux[p]), 'ratio': r,
                       'hf_lf': float(hf[p:p + 3].max() / (lf[p:p + 3].max() + 1e-6))})
    json.dump({'dur': len(x) / SR, 'hits': ev}, open(out, 'w'))
    print(src.split('/')[-1], f'{len(x)/SR:.0f}s', len(ev), 'hits', [round(e['t'], 1) for e in ev][:40])

if __name__ == '__main__':
    if len(sys.argv) > 2:
        detect(sys.argv[1], sys.argv[2])
    else:
        import os
        import project as P
        os.makedirs('hits', exist_ok=True)
        for c in P.clips():
            if not os.path.exists(f'hits/{c}.json'):
                detect(P.mp4(c), f'hits/{c}.json')
