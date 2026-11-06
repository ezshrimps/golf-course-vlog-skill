"""按 edl 拼接原声（每段两端 40ms 淡变），输出 wav。用法: python audio.py edl.json out.wav"""
import sys, json, subprocess, numpy as np
import project as P

SR = 48000
FPS = 60000 / 1001
edl = json.load(open(sys.argv[1], encoding='utf-8'))
chunks = []
for seg in edl['segments']:
    mp4 = P.mp4(seg['clip'])
    # 与视频帧数严格对齐
    nfr = int(round((seg['out'] - seg['in']) * FPS))
    n = int(round(nfr / FPS * SR))
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{seg["in"]:.3f}', '-i', mp4, '-t', f'{seg["out"] - seg["in"] + 0.2:.3f}',
                          '-vn', '-ac', '2', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).reshape(-1, 2).astype(np.float32)
    if len(a) < n:
        a = np.vstack([a, np.zeros((n - len(a), 2), np.float32)])
    a = a[:n]
    g = seg.get('gain', 1.0)
    f = int(0.04 * SR)
    ramp = np.linspace(0, 1, f)[:, None]
    a[:f] *= ramp; a[-f:] *= ramp[::-1]
    chunks.append(a * g)
out = np.clip(np.vstack(chunks), -32768, 32767).astype(np.int16)
import wave
w = wave.open(sys.argv[2], 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes()); w.close()
print('audio', len(out) / SR, 's')
