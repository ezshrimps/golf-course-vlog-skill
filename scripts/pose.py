"""对全部片段的 LRF 代理跑 YOLO pose（约 10fps），存每帧人物关键点和裤子颜色到 pose/<clip>.npz。
坐标统一为 1280x720（没有 LRF 时把原片缩到这个尺寸）。用法: python pose.py"""
import cv2, numpy as np
from ultralytics import YOLO

model = YOLO('yolo11m-pose.pt')

def process(src, out):
  global recs, batch, times
  cap = cv2.VideoCapture(src)
  fps = cap.get(cv2.CAP_PROP_FPS)
  step = max(1, round(fps / 10))
  recs = []
  batch, times = [], []
  i = 0
  while True:
    ok = cap.grab()
    if not ok:
        break
    if i % step == 0:
        ok, fr = cap.retrieve()
        if fr.shape[1] != 1280:
            fr = cv2.resize(fr, (1280, 720), interpolation=cv2.INTER_AREA)
        batch.append(fr); times.append(i / fps)
        if len(batch) == 32:
            flush()
    i += 1
  flush()
  np.savez_compressed(out, recs=np.array(recs, np.float32), fps=fps, n=i)
  print(src, i / fps, 's', len(recs), flush=True)

recs, batch, times = [], [], []
def flush():
    if not batch:
        return
    res = model(batch, verbose=False, imgsz=736, conf=0.35)
    for t, fr, r in zip(times, batch, res):
        if r.keypoints is None:
            continue
        kp = r.keypoints.data.cpu().numpy()
        bx = r.boxes.xyxy.cpu().numpy()
        cf = r.boxes.conf.cpu().numpy()
        hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
        for j in range(len(bx)):
            k = kp[j]
            # 裤子：髋(11,12)到膝(13,14)之间的区域
            col = np.array([-1, -1, -1], float)
            if k[11, 2] > .4 and k[12, 2] > .4 and k[13, 2] > .4 and k[14, 2] > .4:
                ys = np.linspace(min(k[11, 1], k[12, 1]), max(k[13, 1], k[14, 1]), 6)[1:-1]
                pts = []
                for y in ys:
                    for side in ((11, 13), (12, 14)):
                        a, b = k[side[0]], k[side[1]]
                        tt = (y - a[1]) / max(1, b[1] - a[1])
                        x = a[0] + (b[0] - a[0]) * tt
                        xi, yi = int(x), int(y)
                        if 2 <= xi < fr.shape[1] - 2 and 2 <= yi < fr.shape[0] - 2:
                            pts.append(hsv[yi - 2:yi + 3, xi - 2:xi + 3].reshape(-1, 3))
                if pts:
                    col = np.median(np.concatenate(pts), axis=0)
            # 小腿：膝(13,14)到踝(15,16)，区分长裤和短裤
            col2 = np.array([-1, -1, -1], float)
            pts = []
            for a_, b_ in ((13, 15), (14, 16)):
                a, b = k[a_], k[b_]
                if a[2] > .4 and b[2] > .4:
                    for tt in (.3, .5, .7):
                        xi, yi = int(a[0] + (b[0] - a[0]) * tt), int(a[1] + (b[1] - a[1]) * tt)
                        if 2 <= xi < fr.shape[1] - 2 and 2 <= yi < fr.shape[0] - 2:
                            pts.append(hsv[yi - 2:yi + 3, xi - 2:xi + 3].reshape(-1, 3))
            if pts:
                col2 = np.median(np.concatenate(pts), axis=0)
            recs.append((t, j, *bx[j], cf[j], *k.reshape(-1), *col, *col2))
    batch.clear(); times.clear()


if __name__ == '__main__':
    import os
    import project as P
    os.makedirs('pose', exist_ok=True)
    for id_ in P.clips():
        out = f'pose/{id_}.npz'
        if not os.path.exists(out):
            process(P.lrf(id_), out)
    print('ALL DONE')
