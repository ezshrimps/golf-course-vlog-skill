"""给一首速度恒定的歌拟合节拍网格，并把网格对到底鼓上，输出 beats.npy 给 songcut.py。
用法: python song_grid.py song.mp3 大约BPM [out=beats.npy]
librosa 的节拍跟踪常锁在踩镲（"次"）上；这里用 30–90Hz 底鼓起音在一拍内的相位把网格挪到"动"上。"""
import sys, numpy as np, librosa

F, bpm = sys.argv[1], float(sys.argv[2])
out = sys.argv[3] if len(sys.argv) > 3 else 'beats.npy'
y, sr = librosa.load(F, sr=44100)
hop = 128; dt = hop / sr
yp = librosa.effects.percussive(y, margin=3)
o = librosa.onset.onset_strength(y=yp, sr=sr, hop_length=hop)
_, b = librosa.beat.beat_track(onset_envelope=o, sr=sr, hop_length=hop, tightness=300, start_bpm=bpm)
w = int(0.06 / dt)
bt = np.array([(max(0, f - w) + np.argmax(o[max(0, f - w):f + w + 1])) * dt for f in b])

# 全曲网格：相位一致性最高的周期
P0 = 60 / bpm
z, P = max((abs(np.mean(np.exp(2j * np.pi * bt / P))), P) for P in np.arange(P0 * 0.985, P0 * 1.015, 0.00002))
t0 = np.angle(np.mean(np.exp(2j * np.pi * bt / P))) / (2 * np.pi) * P
r = bt - (t0 + np.round((bt - t0) / P) * P)
for _ in range(3):   # 只用贴合网格的拍（|残差|<20ms，跳过 fill / 间奏）做最小二乘精修
    k = np.round((bt - t0) / P); m = abs(r) < 0.02
    P, t0 = np.polyfit(k[m], bt[m], 1)
    r = bt - (t0 + np.round((bt - t0) / P) * P)
print(f'grid BPM {60 / P:.3f}  coherence {z:.2f}  |resid|<20ms {np.mean(abs(r) < 0.02):.0%}')

# 各频段起音在一拍内的相位（0 = 网格点）
S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop)); f = librosa.fft_frequencies(sr=sr, n_fft=2048)
gb = t0 + np.arange(np.ceil(-t0 / P), (len(y) / sr - t0) / P - 1) * P
nb = int(round(P / dt))
def phase(lo, hi):
    env = np.log1p(S[(f > lo) & (f < hi)].sum(0))
    on = np.maximum(0, np.diff(env, prepend=env[0]))
    fold = np.zeros(nb)
    for t in gb:
        i = int(round(t / dt))
        if i + nb <= len(on):
            fold += on[i:i + nb]
    return int(np.argmax(fold)) * dt
for name, lo, hi in [('kick 30-90Hz', 30, 90), ('bass 90-200Hz', 90, 200), ('hat >6kHz', 6000, 16000)]:
    print(f'{name:14s} attack at +{phase(lo, hi) * 1000:.0f} ms after grid')
shift = phase(30, 90)
beats = t0 + shift + np.arange(np.ceil(-(t0 + shift) / P), (len(y) / sr - t0 - shift) / P) * P
np.save(out, beats)
print(f'saved {len(beats)} kick beats to {out}  (shift {shift * 1000:+.0f} ms)')
