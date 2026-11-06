---
name: golf-course-vlog
description: Turn a folder of raw golf-round footage (DJI Osmo Pocket style, 4K + LRF proxies) into a full-course vlog with a broadcast-style UI — hole-by-hole HUD, OSM hole maps, swing path tracer, ball flight, estimated ball speed / carry / club cards, dialogue subtitles — plus spin-off cuts (best-shots reel, partner reel, beat-synced swing montage). Use when the user says "剪高尔夫 vlog", "full course vlog", "把打球视频剪成…", "卡点快剪挥杆", or drops a folder of golf round clips.
---

# Golf course vlog（整场高尔夫 vlog 剪辑）

把一场球的原片（几十个片段、约 1–2 小时）剪成一条 15–20 分钟、带 UI 的整场 vlog。核心是一条「检测 → 人工核对 → 剪辑表 EDL → 渲染」的流水线：机器先找出所有挥杆和击球，人只核对机器拿不准的部分，剪辑和 UI 全部由 EDL 驱动，改一处重渲即可。

成片结构：片头标题 → 每个九洞的章节卡 → 每洞（球洞卡 + 全部真挥杆 + 一次空挥 + 少量对话/过场）→ 收尾。

## 依赖

- Windows + NVIDIA GPU（渲染用 `h264_nvenc`，转写和姿态用 CUDA）。字体用系统自带的 Bahnschrift 和微软雅黑（`project.json` 的 `fonts` 可改目录）。
- `ffmpeg` / `ffprobe` 在 PATH 里。
- `pip install -r requirements.txt`（ultralytics、faster-whisper、opencv-python、numpy、scipy、Pillow、librosa）。
- 素材：4K 16:9、59.94fps，按 DJI 命名 `DJI_<YYYYMMDDHHMMSS>_<NNNN>_*.MP4`。文件名里的时间就是每段的开拍时间（HUD 上的钟点从这里来），四位编号是片段号。同名 `.LRF`（1280x720 代理）能让检测快很多；没有也能跑。

## 约定

- **工作目录**：新建一个空文件夹做中间文件（会有十几 GB），不要放在素材文件夹里。所有脚本都在工作目录里运行：`python <skill>/scripts/xxx.py`。
- **坐标**：姿态和人物框都是 1280x720（LRF）坐标；渲染时 ×1.5 到 1080p、×3 到 4K。
- **谁是谁**：靠裤子区分。`swings.legclass` 比较大腿和小腿的颜色，分成 `grey`（长裤）和 `skin`（短裤）。`project.json` 里的 `me_leg` 写用户自己是哪种。如果两个人都穿长裤，这一步会失效，要在 `fixes` 里手动标。
- **击球时刻**：画面上杆头碰球比姿态模型给出的「手最低点」晚约 30ms，相机录到的击球声又比画面晚约 105ms（声音传播加编码延迟）。要卡点就用画面时刻，音频单独往前提。

## 流程

### 0. 准备 `project.json`

把 `templates/project.example.json` 复制到工作目录，改成 `project.json`，然后填：

- `footage`：原片文件夹。
- `center`：球场中心的经纬度。
- `nines`：每个九洞的 par、蓝/白 T 码数和难度（hcp），从 greenskeeper.org、golfpass、球场官网的记分卡上查。键名就是 UI 上显示的九洞名，比如 `MOUNTAIN`、`FRONT`。
- `route`：实际打了哪些洞、按什么顺序。没打完也照实写。
- `tees`：每个洞第一个片段的编号，见第 3 步。
- `course_label`：HUD 左上角显示的球场名。

### 1. 检测（GPU，耗时最长，放后台跑）

```
python scripts/hits.py        # 每段的击球声（2.5–12kHz 瞬态）→ hits/<clip>.json
python scripts/pose.py        # YOLO11m-pose 约 10fps，含裤子颜色 → pose/<clip>.npz
python scripts/asr_all.py     # faster-whisper large-v3 中文转写 → asr/<clip>.json
```

用户还在往文件夹里导素材时，最后一个文件可能没写完，先只处理已完整的片段。

### 2. 球洞地图

```
python scripts/maps.py        # 从 Overpass 下载 OSM 球场数据 → maps/<NINE>_<n>.png
```

每个九洞按 par 序列和记分卡比对，自动认出对应 OSM 里的哪一组。OSM 偶尔会标错一两个 par，相差 2 个以内都能认出来。地图把发球台放在下、果岭放在上，画出 rough/球道走廊、沙坑、果岭和码数刻度。成片里要标注「© OpenStreetMap contributors」。

### 3. 分洞（需要人工看）

素材里**没有 GPS**（DJI 元数据里找过，没有坐标），只能看画面分洞：

```
python scripts/overview.py    # sh/ov_*.jpg：每段一行 7 帧缩略图
```

在缩略图里找发球台的 T 标、洞号牌和开球画面，记下每洞第一个片段，填进 `tees`。再按开拍时间顺序核对一遍：每洞的片段数应该合理，最后几洞要按实际情况写（比如天黑没打完）。

### 4. 挥杆识别 + 人工修正

```
python scripts/swings.py               # pose + hits → swings.json（上杆→击球→收杆，±1s 内有击球声 = 真挥杆）
python scripts/review.py 0001 0020     # sh/rv_*.jpg：每次挥杆一行 5 帧裁剪图
python scripts/finalize.py             # 套用 project.json 的 fixes → events.json
```

逐张看核对图，把问题写进 `project.json` 的 `fixes`（每条是 `[片段号, 秒]`，±0.6s 内都算匹配）：

| 键 | 用途 |
|---|---|
| `drop` | 误检：走路摆臂、捡球、对镜头比划 |
| `real` | 姿态认出了挥杆，但击球声没检测到（推杆、切杆声音小），强制算真挥杆 |
| `partner` / `me` | 腿色认错了人 |
| `add` | 姿态完全没抓到的真挥杆：`[片段号, 击球秒, "me"或"partner"]`。天黑以后常见 |

`swings.json` 里标 `audio_only` 的是只有击球声、没有挥杆动作的事件，要逐个看一眼，确认是不是漏掉的挥杆。

### 5. 逐杆精细分析

```
python scripts/pick_shots.py                              # sel_me.json / sel_partner.json
python scripts/shots.py sel_me.json                       # 60fps 姿态 + 4K 球追踪 → shots/
python scripts/shots.py sel_partner.json shots_p --no-track
```

`swing_detail.analyze` 在原片上用 60fps 跑姿态，找出起杆、上杆顶点、击球、收杆，算出节奏比（上杆时长 : 下杆时长）和手速（按身高 1.70m 把像素换成米）。`balltrack.track` 做帧差找小亮点，从球位上方开始，按速度外推关联成轨迹。`trackcheck.good_track` 再过滤一遍：起点必须在脚踝附近、轨迹要明显上升、曲线要平滑，过不了的当没追到。实测约 1/3 的木杆和铁杆能追到真实球路。

### 6. 剪辑表

把 `templates/edl_cfg.example.json` 复制成 `edl_cfg.json`，然后填：

- `intro` / `outro`：片头和片尾用哪段画面、配什么标题。
- `course_titles`：每个九洞开头的章节卡。
- `extras`：开车、过桥、记分卡、果岭、夕阳这类过场，以及有意思的对话。

对话这样挑：翻 `asr/*.json`，找好笑的、有梗的、在讲球的（比如 mulligan 科普、沙坑教学、果岭上的玩笑）。每段 5–20 秒。字幕放进 `sub` overlay，`at` 是相对段开头的秒数。转写会有错字，字幕要人工改。

```
python scripts/build_edl.py   # → edl.json
```

`build_edl` 的规则：

- 每洞第一杆前留 7.6 秒，同时滑出球洞卡。
- 自己的真挥杆前留 2.8 秒、后留 3.8 秒，并放大构图到人物占画面约一半高。
- 球友的挥杆前留 2.3 秒、后留 2.6 秒，并打上 `PARTNER` 标签。
- 每洞最多保留一次空挥。
- 同一片段里相邻的段，构图一样就合并；构图不一样，就把前一段截短到后一段开始的位置。

`edl_cfg.json` 里的 `drop`、`force_real`、`bunker` 用来最后微调。`bunker` 标出的沙坑球，杆型会显示成 SAND WEDGE。

### 7. 渲染

```
python scripts/make.py out.mp4 4     # 按时长切 4 份并行渲染 + audio.py 拼原声 + 合成
```

`render.py` 的流程是：ffmpeg 解码并裁剪 → PIL 逐帧叠加 UI → NVENC 编码（cq19，约 24Mbps）。UI 各部分如下（都在 `ui.py`）：

- **左上 HUD**：球场名、钟点、九洞标签、洞号、PAR、码数、HCP，下方是全场进度条。
- **球洞卡**：每洞开头从右侧滑入，含地图、蓝/白 T 码数和难度。
- **挥杆轨迹**：手部点逐帧生长，上杆白色，下杆和收杆用荧光绿。
- **球路**：追到真实球路的画实线，标 `BALL TRACKED`；没追到的画透视示意弧线，标 `PREDICTED FLIGHT`。
- **数据卡**：显示杆型、球速、飞行距离和节奏比，标 `EST.`。
- **其他**：标签、字幕、章节标题。

一场 20 分钟的 4K 素材，在 4070 Ti 上大约要 25 分钟。成片约 5GB。另外导一份压缩版发手机：

```
ffmpeg -i out.mp4 -c:v libx264 -crf 23 -preset slow -c:a aac -b:a 160k -movflags +faststart out_small.mp4
```

### 8. 交付前检查

- 按时间均匀抽几十帧看 UI 和洞号对不对：`python scripts/sheet.py out.mp4 sheet.jpg 0 1200 20`。
- 跟用户说清楚：球速、飞行距离和杆型都是**估算**。球速 = 手速 × 杆长系数 × 击球效率；杆型在发球台按洞型判断，其他位置只按挥杆幅度分 IRON / PITCH / CHIP。没追到球的球路只是示意，不代表球实际的方向。
- 写清楚漏了什么：没拍到的杆、天黑后识别变差、人工补过哪些杆。

## 衍生剪辑

前面的数据都能复用，不用重新检测：

- **满意球精华**：`python scripts/hold.py` 测出每杆击球后双手停在肩膀以上（收杆姿势）的时长。停得越久，说明打的人越满意。先用 `python scripts/holdsheet.py 1.5 9` 看核对图，在 `edl_cfg.json` 的 `highlights.hold_sec` 里定门槛（实测中位数约 1.1 秒，门槛 2 秒能选出约 1/5 的球）。然后 `python scripts/build_edl2.py me`，再 `python scripts/make2.py edl_me.json best.mp4`。这个版本不画挥杆轨迹和球路，右上角常驻小地图。
- **球友全部出杆**：`python scripts/build_edl2.py partner`，再 `python scripts/make2.py edl_partner.json partner.mp4`。
- **下杆快剪**（每杆只留上杆顶点到击球）：先 `python scripts/downswings.py`，再 `python scripts/refine.py`（用击球声精修击球时刻），然后 `python scripts/fastcut.py out.mp4 all 1.2`。
- **合成鼓点卡点**：`python scripts/beatcut.py out.mp4 all 1.2`。BPM 定成 149.85，一拍正好是 60fps 下的 24 帧，越往后也不会漂。每杆一拍，击球帧落在底鼓上。
- **配用户自己的歌卡点**：
  ```
  python scripts/song_grid.py song.mp3 150 beats.npy
  MUS=0.2 HIT=0.9 python scripts/songcut.py out.mp4 song.mp3 beats.npy <起始秒> 1.2
  ```
  - 要对准的是**底鼓「动」**，不是踩镲「次」。librosa 的节拍跟踪经常锁在踩镲上，差半拍。`song_grid.py` 会打印各频段起音在一拍内的位置，再把网格挪到 30–90Hz 的底鼓起音上。
  - 起始秒要选在一个强拍上，避开 fill 和间奏。
  - 歌里有无鼓的停顿时，加 `BREAK=起,止,拍数`，在停顿里均分补拍。
  - 用户通常希望击球声盖过音乐：`MUS` 压低音乐，`HIT` 把每杆击球瞬间（击球前 30ms 到击球后 180ms）放大到统一峰值，最多放大 8 倍。
  - 不同长度的段直接用 `-c copy` 拼接，时间戳会重叠，画面整体会提前几帧。`songcut.py` 改成了按帧序号重排时间戳再重编码。
  - 受版权保护的歌不要替用户下载，让用户自己提供音频文件。

## 踩过的坑

- 用户还在导素材时就开跑，最后一个文件会读到一半。
- 原片在剪辑中途被挪进子文件夹，所有路径都要跟着改。现在只需要改 `project.json` 的 `footage`。
- 天黑以后 YOLO 姿态会丢人，最后两洞要靠 `fixes.add` 人工补。
- 手持跟拍的片段放大后会把人裁出画面，这类段不要设 `zoom`。
- 磁盘：中间文件约 15GB，4K 成片约 5GB。开跑前先看素材盘和工作盘的剩余空间。
