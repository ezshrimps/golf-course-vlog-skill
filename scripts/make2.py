"""渲染单个 edl（拆 2 段并行）+ 音频 + 合成。用法: python make2.py edl.json out.mp4"""
import sys, json, subprocess
edl_f, out = sys.argv[1], sys.argv[2]
tag = edl_f.replace('.json', '')
n = len(json.load(open(edl_f, encoding='utf-8'))['segments'])
mid = n // 2
ps = [subprocess.Popen(['python', '-u', 'render.py', edl_f, f'{tag}_p0.mp4', '0', str(mid)], stdout=open(f'log_{tag}_0.txt', 'w'), stderr=subprocess.STDOUT),
      subprocess.Popen(['python', '-u', 'render.py', edl_f, f'{tag}_p1.mp4', str(mid), str(n)], stdout=open(f'log_{tag}_1.txt', 'w'), stderr=subprocess.STDOUT),
      subprocess.Popen(['python', 'audio.py', edl_f, f'{tag}.wav'], stdout=open(f'log_{tag}_a.txt', 'w'), stderr=subprocess.STDOUT)]
for p in ps:
    p.wait()
open(f'{tag}_parts.txt', 'w').write(f"file '{tag}_p0.mp4'\nfile '{tag}_p1.mp4'\n")
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{tag}_parts.txt', '-i', f'{tag}.wav',
                '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart',
                '-shortest', out], check=True)
print('done', out)
