#!/usr/bin/env python3
import json
from pathlib import Path

SRC=Path('/root/.openclaw/workspace/transcripts/full_pass_candidates.json')
OUT=Path('/root/.openclaw/workspace/transcripts/full_pass_candidates_filtered.json')

candidates=json.loads(SRC.read_text(encoding='utf-8'))
filtered=[]
per_video={}
per_topic={}
for c in candidates:
    topic=c['topic']
    vid=c['video_id']
    text=c['text'].lower()
    if per_video.get(vid,0) >= 4:
        continue
    if per_topic.get(topic,0) >= 60:
        continue
    if topic == 'entry_pricing' and not any(tok in text for tok in ['price','fair value','limit order','overbought','discount','spread','filled','fill','odds']):
        continue
    if topic == 'timing_setup' and not any(tok in text for tok in ['headline','clip','q&a','east room','late','timing','reaction','briefing','rally','guest']):
        continue
    if topic == 'risk_disputes' and not any(tok in text for tok in ['dispute','resolved','resolve','partial','live','volatility','risk']):
        continue
    filtered.append(c)
    per_video[vid]=per_video.get(vid,0)+1
    per_topic[topic]=per_topic.get(topic,0)+1

OUT.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'filtered_count': len(filtered),
    'per_topic': per_topic,
    'unique_videos': len({c['video_id'] for c in filtered}),
}, ensure_ascii=False, indent=2))
print('OUT', OUT)
