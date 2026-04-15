#!/usr/bin/env python3
import argparse, json, subprocess
from market_pipeline.query import retrieve_bundle
from market_pipeline.select import select_bundle

KALSHI='/root/.openclaw/workspace/kalshi/kalshi_cli.py'
PRESETS={
    'trump-live-qa': {'speaker':'Trump','format':'press conference','archetype':'trump live q&a mention market','event_classes':['trump-live-qa','briefing-style']},
    'trump-rally': {'speaker':'Trump','format':'rally','archetype':'trump live q&a mention market','event_classes':['trump-rally']},
    'announcer-market': {'speaker':'','format':'announcer market','archetype':'recurring announcer mention market','event_classes':['announcer-market']},
    'earnings-call': {'speaker':'','format':'earnings call','archetype':'','event_classes':['earnings-call']},
}

def run(cmd): return subprocess.check_output(cmd, text=True)

def fetch_event(ticker): return run(['python3', KALSHI, 'event', ticker, '--pretty'])

def parse_event_title(raw):
    for line in raw.splitlines():
        if line.startswith('Title: '): return line.split('Title: ',1)[1].strip()
    return 'Unknown event'

def analyze_event(ticker,preset='',speaker='',fmt='',archetype='',event_classes=None,freeform='',top=4):
    event_raw=fetch_event(ticker)
    event_title=parse_event_title(event_raw)
    p=PRESETS.get(preset,{}) if preset else {}
    speaker=speaker or p.get('speaker','')
    fmt=fmt or p.get('format','')
    archetype=archetype or p.get('archetype','')
    ecs=list(p.get('event_classes',[]))+list(event_classes or [])
    retrieval=retrieve_bundle(event_title,speaker,fmt,archetype,freeform,ecs,top)
    bundle=select_bundle(retrieval)
    return {'ticker': ticker,'event_title': event_title,'classification': {'speaker': speaker,'format': fmt,'archetype': archetype,'event_classes': ecs},'kb_bundle': bundle,'event_raw': event_raw}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('ticker'); ap.add_argument('--preset', default=''); ap.add_argument('--speaker', default=''); ap.add_argument('--format', dest='fmt', default=''); ap.add_argument('--archetype', default=''); ap.add_argument('--event-class', action='append'); ap.add_argument('--freeform', default=''); ap.add_argument('--top', type=int, default=4); args=ap.parse_args()
    print(json.dumps(analyze_event(args.ticker,args.preset,args.speaker,args.fmt,args.archetype,args.event_class,args.freeform,args.top), indent=2, ensure_ascii=False))

if __name__=='__main__':
    main()
