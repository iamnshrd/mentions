#!/usr/bin/env python3
import json, sys
from collections import Counter


def summarize(classified_rows, report=None):
    bucket_counts = Counter(r.get('bucket', 'unknown') for r in classified_rows)
    confidence_counts = Counter(r.get('confidence', 'unknown') for r in classified_rows)
    low_conf = [r.get('label') for r in classified_rows if r.get('confidence') == 'low']
    tbd = []
    for r in classified_rows:
        if str(r.get('fv', '')).startswith('TBD'):
            tbd.append(r.get('label'))
    out = {
        'bucket_counts': dict(bucket_counts),
        'confidence_counts': dict(confidence_counts),
        'low_confidence_labels': low_conf,
        'tbd_fv_labels': tbd,
    }
    if report:
        out['report_fields'] = {
            'title': report.get('title'),
            'best_basket': report.get('best_basket'),
            'difficulty': report.get('difficulty'),
            'regime': report.get('regime'),
        }
    return out


if __name__ == '__main__':
    payload = json.load(sys.stdin)
    print(json.dumps(summarize(payload.get('classified', []), payload.get('report')), indent=2, ensure_ascii=False))
