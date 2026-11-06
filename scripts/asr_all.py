"""转写全部片段的对话（faster-whisper large-v3），输出 asr/<clip>.json"""
import json, os, subprocess, tempfile
from faster_whisper import WhisperModel
import project as P
m = WhisperModel('large-v3', device='cuda', compute_type='float16')
os.makedirs('asr', exist_ok=True)
for id_ in P.clips():
    f = P.lrf(id_)
    out = f'asr/{id_}.json'
    if os.path.exists(out): continue
    wav = tempfile.mktemp(suffix='.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f, '-vn', '-ac', '1', '-ar', '16000', wav], check=True)
    segs, _ = m.transcribe(wav, language='zh', vad_filter=True, beam_size=5,
                           initial_prompt='两个朋友在高尔夫球场打球聊天，简体中文。')
    res = [{'s': s.start, 'e': s.end, 't': s.text.strip(), 'p': s.avg_logprob, 'ns': s.no_speech_prob} for s in segs]
    os.remove(wav)
    json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(id_, len(res), flush=True)
print('ASR DONE')
