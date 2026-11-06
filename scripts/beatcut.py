"""卡点快剪：每杆 24 帧（一拍），击球帧落在第 IMPF 帧 = 底鼓。
用法: python beatcut.py out.mp4 idx...|all [speed]"""
import sys, json, subprocess, os, wave, numpy as np
import beat

import project as P
FPS = 60000 / 1001
NF = 24            # 每杆帧数 = 一拍
IMPF = 16          # 击球在第 16 帧
SPD = float(sys.argv[3]) if len(sys.argv) > 3 else 1.2
INTRO = 2 * beat.BEAT   # 开头留两拍 riser
rows = [r for r in json.load(open('downswings.json')) if 0.1 < r['down'] < 0.6]
sel = rows if sys.argv[2] == 'all' else [rows[int(i)] for i in sys.argv[2].split(',')]
os.makedirs('bc', exist_ok=True)
SR = beat.SR

def crop_args(r):
    x0, y0, x1, y1 = [v * 3 for v in r['box']]
    h = max(900, (y1 - y0) * 1.7); w = min(h * 16 / 9, 3840); h = w * 9 / 16
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 - 0.05 * h
    x = min(max(0, cx - w / 2), 3840 - w); y = min(max(0, cy - h / 2), 2160 - h)
    return f'crop={int(w)//2*2}:{int(h)//2*2}:{int(x)}:{int(y)}'

parts, sfx = [], []
for k, r in enumerate(sel):
    vis = r['imp'] + 0.030                                     # 画面上杆头触球
    a = vis - IMPF / FPS * SPD                                 # 原片里的起点
    off = r['imp_a'] - vis if r['imp_a'] != r['imp'] and 0.05 < r['imp_a'] - vis < 0.2 else 0.105
    aa = a + off                                               # 原声比画面晚 off，提前取
    src = P.mp4(r['clip'])
    out = f'bc/{k:03d}.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{a:.4f}', '-i', src, '-an',
                    '-vf', f'{crop_args(r)},scale=1920:1080:flags=lanczos,setsar=1,setpts=(PTS-STARTPTS)/{SPD},fps=60000/1001',
                    '-frames:v', str(NF), '-c:v', 'libx264', '-preset', 'fast', '-crf', '16', '-pix_fmt', 'yuv420p', out], check=True)
    parts.append(out)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{aa:.4f}', '-i', src, '-t', f'{NF / FPS * SPD + 0.05:.4f}', '-vn',
                          '-af', f'atempo={SPD}', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
    s = np.frombuffer(raw, np.float32).reshape(-1, 2)[:int(NF / FPS * SR)]
    sfx.append(s)

# 开头黑场两拍
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=1920x1080:r=60000/1001',
                '-frames:v', str(2 * NF), '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p', 'bc/intro.mp4'], check=True)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=1920x1080:r=60000/1001',
                '-frames:v', str(int(1.6 * FPS)), '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p', 'bc/outro.mp4'], check=True)
with open('bc/list.txt', 'w') as f:
    for p in ['bc/intro.mp4'] + parts + ['bc/outro.mp4']:
        f.write(f"file '{os.path.basename(p)}'\n")
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', 'bc/list.txt', '-c', 'copy', 'bc/video.mp4'], check=True)

# 音频：音乐 + 原声（每段两端 8ms 淡变）
first = INTRO + IMPF / FPS
mus = beat.music(len(sel), first)
mix = mus * 0.75
f8 = int(0.008 * SR); ramp = np.linspace(0, 1, f8)[:, None]
for k, s in enumerate(sel and sfx):
    s = s.copy(); s[:f8] *= ramp; s[-f8:] *= ramp[::-1]
    i = int(round((INTRO + k * NF / FPS) * SR))
    m = min(len(s), len(mix) - i)
    mix[i:i + m] += s[:m] * 0.9
mix = mix / max(1.0, np.abs(mix).max() / 0.95)
w = wave.open('bc/mix.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((mix * 32767).astype(np.int16).tobytes()); w.close()
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', 'bc/video.mp4', '-i', 'bc/mix.wav', '-map', '0:v', '-map', '1:a',
                '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', sys.argv[1]], check=True)
print(len(sel), 'shots', f'{(2 * NF + len(sel) * NF) / FPS + 1.6:.1f}s', f'BPM {60 / beat.BEAT:.2f}')
