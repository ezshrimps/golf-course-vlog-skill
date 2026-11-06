"""合成鼓点音乐：每拍 24 帧(60000/1001)，击球落在每拍的 kick 上。
music(n_beats, first_beat_at) -> float32 stereo @48k"""
import numpy as np

SR = 48000
BEAT = 24 * 1001 / 60000          # 0.4004 s ≈ 149.85 BPM
rng = np.random.default_rng(7)

def env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)

def kick():
    n = int(0.32 * SR); t = np.arange(n) / SR
    f = 48 + 110 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * env(n, 0.001, 0.16)
    click = rng.standard_normal(n) * env(n, 0.0005, 0.004) * 0.4
    return np.tanh((body + click) * 2.2) * 0.9

def snare():
    n = int(0.25 * SR); t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * 190 * t) * env(n, 0.001, 0.05) * 0.5
    noise = rng.standard_normal(n)
    noise = np.convolve(noise, [1, -0.85], 'same') * env(n, 0.001, 0.09)
    return np.tanh((tone + noise * 0.6) * 1.6) * 0.55

def clap():
    n = int(0.22 * SR)
    out = np.zeros(n)
    for o in (0, 0.009, 0.018):
        k = int(o * SR)
        out[k:] += rng.standard_normal(n - k) * env(n - k, 0.0005, 0.03 if o < 0.018 else 0.08)
    return np.convolve(out, [1, -0.9], 'same') * 0.35

def hat(open_=False):
    n = int((0.18 if open_ else 0.05) * SR)
    x = np.convolve(rng.standard_normal(n), [1, -1], 'same')
    return x * env(n, 0.0005, 0.06 if open_ else 0.012) * 0.18

def bass(freq, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    saw = 2 * ((t * freq) % 1) - 1
    sub = np.sin(2 * np.pi * freq / 2 * t)
    x = 0.45 * saw + 0.7 * sub
    # 简单低通
    a = 0.06
    y = np.zeros(n)
    for i in range(1, n):
        y[i] = y[i - 1] + a * (x[i] - y[i - 1])
    return np.tanh(y * 2.5) * env(n, 0.004, dur * 0.9) * 0.5

def add(buf, x, at):
    i = int(round(at * SR))
    if i >= len(buf) or i + len(x) <= 0:
        return
    j0 = max(0, -i); x = x[j0:]; i = max(0, i)
    m = min(len(x), len(buf) - i)
    buf[i:i + m] += x[:m]

def music(n_beats, first, tail=1.6):
    total = first + n_beats * BEAT + tail
    L = np.zeros(int(total * SR)); R = np.zeros_like(L)
    K, S, C = kick(), snare(), clap()
    # 低音走向（E 小调：E E G D）每小节一个根音
    roots = [41.2, 41.2, 49.0, 36.7]
    for b in range(n_beats):
        t = first + b * BEAT
        bar, pos = divmod(b, 4)
        for buf in (L, R):
            add(buf, K, t)
        if pos in (1, 3):
            add(L, S, t); add(R, S, t)
            add(L, C * 0.8, t + 0.002); add(R, C, t)
        # hats：8 分 + 每小节末 16 分
        for h in range(2):
            ht = t + h * BEAT / 2
            hh = hat(open_=(h == 1 and pos == 3))
            add(L, hh * (0.8 if h else 1.0), ht); add(R, hh * (1.0 if h else 0.8), ht)
        if pos == 3:
            for h in (0.25, 0.75):
                add(L, hat() * 0.7, t + h * BEAT); add(R, hat() * 0.7, t + h * BEAT)
        bl = bass(roots[bar % 4], BEAT * 0.95)
        add(L, bl, t); add(R, bl, t)
    # 开头 riser（击球前的加速感）
    if first > 0.3:
        n = int(first * SR); x = rng.standard_normal(n) * np.linspace(0, 1, n) ** 2 * 0.12
        add(L, x, 0); add(R, x, 0)
    # 收尾：最后一击后的 crash + 余音
    end = first + n_beats * BEAT
    n = int(1.4 * SR); crash = np.convolve(rng.standard_normal(n), [1, -0.6], 'same') * env(n, 0.001, 0.45) * 0.25
    add(L, crash, end); add(R, crash, end); add(L, K, end); add(R, K, end)
    out = np.stack([L, R], 1)
    return (out / max(1e-6, np.abs(out).max()) * 0.85).astype(np.float32)
