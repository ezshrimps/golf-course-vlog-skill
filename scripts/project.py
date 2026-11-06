"""读取工作目录下的 project.json（素材位置、球场记分卡、分洞），所有脚本共用。
素材按 DJI 命名：DJI_<YYYYMMDDHHMMSS>_<NNNN>_*.MP4，同名 .LRF 为 1280x720 代理文件（可选）。"""
import json, glob, os, re, datetime

CFG = json.load(open('project.json', encoding='utf-8'))
V = CFG['footage']
ME = CFG.get('me_leg', 'grey')                  # 'grey' = 长裤，'skin' = 短裤（见 swings.legclass）
PARTNER = 'skin' if ME == 'grey' else 'grey'
SCORE = CFG['nines']                            # {九洞名: {par, blue, white, hcp}}
ROUTE = [tuple(h) for h in CFG['route']]        # 实际打过的洞，按顺序
TEES = [tuple(t) for t in CFG['tees']]          # (该洞第一个片段号, 九洞名, 洞号)
LABEL = CFG.get('course_label', 'GOLF CLUB')
FONTS = CFG.get('fonts', 'C:/Windows/Fonts/')

_PAT = re.compile(r'_(\d{14})_(\d{4})_')

def _index():
    out = {}
    for p in glob.glob(os.path.join(V, '*.MP4')):
        m = _PAT.search(os.path.basename(p))
        if m:
            out[m.group(2)] = (p, m.group(1))
    return out

_IDX = _index()

def clips():
    return sorted(_IDX)

def mp4(clip):
    return _IDX[clip][0]

def lrf(clip):
    """低清代理；没有就退回原片（pose.py 会统一缩到 1280x720）"""
    p = mp4(clip)[:-4] + '.LRF'
    return p if os.path.exists(p) else mp4(clip)

def start(clip):
    return datetime.datetime.strptime(_IDX[clip][1], '%Y%m%d%H%M%S')

def clock(clip, t):
    return (start(clip) + datetime.timedelta(seconds=t)).strftime('%I:%M %p').lstrip('0')
