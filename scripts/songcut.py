"""高尔夫卡点：按歌曲实际鼓点逐拍对齐。用法: [MUS=0.2 HIT=0.9 BREAK=a,b[,n]] python songcut.py out.mp4 song.mp3 beats.npy start_sec [speed]
MUS 音乐音量，HIT 击球声峰值（把击球声拉到盖过音乐），BREAK=起,止[,拍数] 歌里无鼓停顿的位置（在其中均分补拍）。"""
import sys, json, subprocess, os, wave, numpy as np
import project as P
FPS = 60000 / 1001; IMPF = 16; SR = 48000
out, song, bfile, start = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
SPD = float(sys.argv[5]) if len(sys.argv) > 5 else 1.2
rows = [r for r in json.load(open('downswings.json')) if 0.1 < r['down'] < 0.6]

# 清理鼓点：去掉过近的多余拍，把偏离两侧中点的拍拉回中点
b = list(np.load(bfile))
i = 1
while i < len(b):
    if b[i] - b[i - 1] < 0.30: b.pop(i)
    else: i += 1
b = np.array(b)
while True:  # 补上漏掉的拍
    d = np.diff(b); j = np.where(d > 0.65)[0]
    if not len(j): break
    b = np.insert(b, j[0] + 1, b[j[0]] + d[j[0]] / 2)
for i in range(1, len(b) - 1):
    mid = (b[i - 1] + b[i + 1]) / 2
    if 0.72 < b[i + 1] - b[i - 1] < 0.88 and abs(b[i] - mid) > 0.035: b[i] = mid
# 无鼓停顿：节拍跟踪在里面会乱，按停顿两端的拍均分
if os.environ.get('BREAK'):
    v = os.environ['BREAK'].split(',')            # 起,止[,拍数]；不给拍数就按中位拍长估
    t1, t2 = float(v[0]), float(v[1])
    lo, hi = np.argmin(np.abs(b - t1)), np.argmin(np.abs(b - t2))
    n = int(v[2]) if len(v) > 2 else int(round((b[hi] - b[lo]) / np.median(np.diff(b))))
    b = np.concatenate([b[:lo], np.linspace(b[lo], b[hi], n + 1), b[hi + 1:]])
s = int(np.argmin(np.abs(b - start)))
B = b[s:s + len(rows) + 1]
assert len(B) == len(rows) + 1, 'song too short'
ibi = np.diff(B); print('IBI range ms', int(ibi.min() * 1000), int(ibi.max() * 1000))
LEAD = 1.6                                 # 先放 1.6 秒音乐
T0 = B[0] - LEAD                           # 视频 0 秒对应歌曲时间
bound = [int(round((t - T0) * FPS)) - IMPF for t in B]   # 每段起始帧
def crop_args(r):
    x0, y0, x1, y1 = [v * 3 for v in r['box']]
    h = max(900, (y1 - y0) * 1.7); w = min(h * 16 / 9, 3840); h = w * 9 / 16
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 - 0.05 * h
    x = min(max(0, cx - w / 2), 3840 - w); y = min(max(0, cy - h / 2), 2160 - h)
    return f'crop={int(w)//2*2}:{int(h)//2*2}:{int(x)}:{int(y)}'
os.makedirs('sc', exist_ok=True)
parts, sfx = [], []
for k, r in enumerate(rows):
    nf = bound[k + 1] - bound[k]
    vis = r['imp'] + 0.030; a = vis - IMPF / FPS * SPD
    off = r['imp_a'] - vis if r['imp_a'] != r['imp'] and 0.05 < r['imp_a'] - vis < 0.2 else 0.105
    src = P.mp4(r['clip']); p = f'sc/{k:03d}.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{a:.4f}', '-i', src, '-an',
                    '-vf', f'{crop_args(r)},scale=1920:1080:flags=lanczos,setsar=1,setpts=(PTS-STARTPTS)/{SPD},fps=60000/1001',
                    '-frames:v', str(nf), '-c:v', 'libx264', '-preset', 'fast', '-crf', '16', '-pix_fmt', 'yuv420p', p], check=True)
    parts.append(p)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{a + off:.4f}', '-i', src, '-t', f'{nf / FPS * SPD + 0.05:.4f}', '-vn',
                          '-af', f'atempo={SPD}', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
    sfx.append(np.frombuffer(raw, np.float32).reshape(-1, 2)[:int(nf / FPS * SR)])
TAIL = 2.4
for name, nf in (('intro', bound[0]), ('outro', int(TAIL * FPS))):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=1920x1080:r=60000/1001',
                    '-frames:v', str(nf), '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p', f'sc/{name}.mp4'], check=True)
with open('sc/list.txt', 'w') as f:
    for p in ['sc/intro.mp4'] + parts + ['sc/outro.mp4']: f.write(f"file '{os.path.basename(p)}'\n")
# 各段帧数不等，直接 copy 拼接时间戳会重叠；按帧序号重排时间戳后重编码
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', 'sc/list.txt', '-fps_mode', 'passthrough',
                '-vf', 'setpts=N/(60000/1001)/TB', '-c:v', 'libx264', '-preset', 'fast', '-crf', '16', '-pix_fmt', 'yuv420p',
                '-video_track_timescale', '60000', 'sc/video.mp4'], check=True)
total = (bound[-1] + int(TAIL * FPS)) / FPS
raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{T0:.4f}', '-i', song, '-t', f'{total:.4f}',
                      '-af', f'afade=t=in:d=0.3,afade=t=out:st={total - TAIL:.3f}:d={TAIL}', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'],
                     capture_output=True).stdout
MUS = float(os.environ.get('MUS', 0.7)); HIT = float(os.environ.get('HIT', 1.0))
mix = np.frombuffer(raw, np.float32).reshape(-1, 2).copy() * MUS
f8 = int(0.008 * SR); ramp = np.linspace(0, 1, f8)[:, None]
for k, x in enumerate(sfx):
    x = x.copy(); x[:f8] *= ramp; x[-f8:] *= ramp[::-1]
    if HIT != 1.0:   # 击球瞬间（-30ms ~ +180ms）放大到峰值 HIT，最多 8 倍
        c = int(IMPF / FPS * SR); g = np.ones(len(x)); a0 = c - int(0.03 * SR); a1 = min(c + int(0.18 * SR), len(x) - int(0.01 * SR) - 1)
        pk = np.abs(x[c - int(0.02 * SR):c + int(0.06 * SR)]).max() + 1e-6; G = float(np.clip(HIT / pk, 1, 8)); g[a0:a1] = G; r = int(0.01 * SR); g[a0 - r:a0] = np.linspace(1, G, r); g[a1:a1 + r] = np.linspace(G, 1, r)
        x *= g[:, None]
    i = int(round(bound[k] / FPS * SR)); m = min(len(x), len(mix) - i); mix[i:i + m] += x[:m] * 0.9
mix = mix / max(1.0, np.abs(mix).max() / 0.97)
w = wave.open('sc/mix.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((mix * 32767).astype(np.int16).tobytes()); w.close()
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', 'sc/video.mp4', '-i', 'sc/mix.wav', '-map', '0:v', '-map', '1:a',
                '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', out], check=True)
json.dump({'T0': T0, 'impact_frames': [bnd + IMPF for bnd in bound[:-1]]}, open('sc/meta.json', 'w'))
print(len(rows), 'shots', f'{total:.1f}s', f'song {T0:.2f}-{T0 + total:.2f}s')
