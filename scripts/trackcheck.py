import numpy as np

def good_track(track, ankle):
    """过滤假追踪：起点在球位附近、明显上升、轨迹平滑"""
    if not track or len(track) < 10:
        return False
    T = np.array(track)
    dt, x, y = T[:, 0], T[:, 1], T[:, 2]
    ax, ay = ankle
    if ax != ax:
        return False
    if not (ay - 380 < y[0] < ay + 30 and abs(x[0] - ax) < 300):
        return False
    if y[0] - y.min() < 150:
        return False
    rx = x - np.polyval(np.polyfit(dt, x, 3), dt)
    ry = y - np.polyval(np.polyfit(dt, y, 3), dt)
    if float(np.sqrt(np.mean(rx ** 2 + ry ** 2))) < 8.0:
        return True
    # 长弧线用二阶差分判断平滑
    d2 = np.hypot(np.diff(x, 2), np.diff(y, 2))
    return len(track) >= 30 and float(np.median(d2)) < 2.5
