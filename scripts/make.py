"""并行渲染 + 拼接 + 混音。用法: python make.py out.mp4 [nparts]"""
import sys, json, subprocess, os

out = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 3
edl = json.load(open('edl.json', encoding='utf-8'))
segs = edl['segments']
# 按时长均分
tot = sum(s['out'] - s['in'] for s in segs)
bounds, acc, k = [0], 0, 1
for i, s in enumerate(segs):
    acc += s['out'] - s['in']
    if acc >= tot * k / N and k < N:
        bounds.append(i + 1); k += 1
bounds.append(len(segs))
procs = []
for p in range(N):
    a, b = bounds[p], bounds[p + 1]
    procs.append(subprocess.Popen(['python', '-u', 'render.py', 'edl.json', f'part{p}.mp4', str(a), str(b)],
                                  stdout=open(f'log_render_{p}.txt', 'w'), stderr=subprocess.STDOUT))
aud = subprocess.Popen(['python', 'audio.py', 'edl.json', 'mix.wav'], stdout=open('log_audio.txt', 'w'),
                       stderr=subprocess.STDOUT)
for p in procs:
    p.wait()
aud.wait()
with open('parts.txt', 'w') as f:
    for p in range(N):
        f.write(f"file 'part{p}.mp4'\n")
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', 'parts.txt', '-i', 'mix.wav',
                '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k',
                '-movflags', '+faststart', '-shortest', out], check=True)
print('done', out)
