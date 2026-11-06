"""上杆顶点→击球的快剪。用法: python fastcut.py out.mp4 idx1,idx2,...|all"""
import sys, json, subprocess
import project as P
rows = json.load(open('downswings.json'))
rows = [r for r in rows if 0.1 < r['down'] < 0.6]
sel = rows if sys.argv[2] == 'all' else [rows[int(i)] for i in sys.argv[2].split(',')]
PRE, POST = 0.05, 0.15
SPD = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
inputs, filt = [], []
for k, r in enumerate(sel):
    a = r['top'] - PRE; dur = r['imp'] + POST - a
    x0, y0, x1, y1 = [v * 3 for v in r['box']]          # LRF(1280) → 4K
    h = max(900, (y1 - y0) * 1.7); w = h * 16 / 9
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 - 0.05 * h
    w = min(w, 3840); h = w * 9 / 16
    x = min(max(0, cx - w / 2), 3840 - w); y = min(max(0, cy - h / 2), 2160 - h)
    inputs += ['-ss', f'{a:.3f}', '-t', f'{dur:.3f}', '-i', P.mp4(r['clip'])]
    filt.append(f'[{k}:v]crop={int(w)//2*2}:{int(h)//2*2}:{int(x)}:{int(y)},scale=1920:1080:flags=lanczos,setsar=1,setpts=PTS/{SPD},fps=60000/1001[v{k}];'
                f'[{k}:a]aresample=48000,afade=t=in:d=0.01,atempo={SPD},afade=t=out:st={dur/SPD-0.02:.3f}:d=0.02[a{k}];')
n = len(sel)
fc = ''.join(filt) + ''.join(f'[v{k}][a{k}]' for k in range(n)) + f'concat=n={n}:v=1:a=1[v][a]'
subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', fc, '-map', '[v]', '-map', '[a]',
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k',
                '-movflags', '+faststart', sys.argv[1]], check=True)
print(n, 'clips', round(sum(r['imp'] + POST - r['top'] + PRE for r in sel) / SPD, 2), 's')
