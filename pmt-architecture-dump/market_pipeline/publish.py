#!/usr/bin/env python3
import argparse, os, subprocess, sys
from pathlib import Path

if __package__ is None or __package__ == '':
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from market_pipeline.report_builder import build_report_json
from market_pipeline.render import render_report
from market_pipeline.validate import validate_report
from market_pipeline.classify_strikes import classify_event
from market_pipeline.diagnostics import summarize
from market_pipeline.wording_enforcer import check_text

NOTES_ROOT = Path('/root/.openclaw/workspace/market-notes')
NOTES_DIR = NOTES_ROOT / 'notes'
INDEX = NOTES_ROOT / 'index.md'


def slugify(s):
    out = []
    for ch in s.lower():
        if ch.isalnum(): out.append(ch)
        elif ch in [' ', '-', '_', '/']: out.append('-')
    slug=''.join(out)
    while '--' in slug:
        slug=slug.replace('--','-')
    return slug.strip('-')


def ensure_index_entry(rel_path, title):
    line = f"- {rel_path.parent.parent.name if False else ''}"
    entry = f"- {title} ({rel_path.name})"
    # keep it simple: only add markdown link if missing
    link = f"- [{title}](notes/{rel_path.name})"
    text = INDEX.read_text() if INDEX.exists() else '# Market Notes Index\n\n'
    if link not in text:
        if not text.endswith('\n'): text += '\n'
        text += link + '\n'
        INDEX.write_text(text)


def git_commit_push(message):
    cmds = [
        ['git', '-C', str(NOTES_ROOT), 'add', '.'],
        ['git', '-C', str(NOTES_ROOT), 'commit', '-m', message],
        ['git', '-C', str(NOTES_ROOT), 'push', 'origin', 'HEAD:master'],
    ]
    for cmd in cmds:
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            if 'commit' in cmd and e.returncode != 0:
                # no changes or commit failure; continue to push if possible
                continue
            raise


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('ticker')
    ap.add_argument('--preset', default='iran-press')
    ap.add_argument('--date', default='2026-04-06')
    ap.add_argument('--slug', default='')
    ap.add_argument('--title', default='')
    ap.add_argument('--push', action='store_true')
    args=ap.parse_args()

    report = build_report_json(args.ticker, args.preset)
    validation = validate_report(report)
    if not validation['ok']:
        raise SystemExit(f"Report validation failed: {validation['errors']}")

    title = args.title or report['title']
    slug = args.slug or slugify(title)
    filename = f"{args.date}-{slug}.md"
    path = NOTES_DIR / filename
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    rendered = render_report(report)
    wording = check_text(rendered, apply_fixes=True, mode='safe')
    rendered = wording['text']
    classified = classify_event(args.ticker, args.preset)
    diag = summarize(classified, report)
    path.write_text(rendered + '\n')
    ensure_index_entry(path, title)

    print(str(path))
    if validation['warnings']:
        print('VALIDATION WARNINGS:')
        for w in validation['warnings']:
            print('-', w)
    if wording['warnings']:
        print('WORDING WARNINGS:')
        for w in wording['warnings']:
            print('-', w)
    print('DIAGNOSTICS:')
    print(diag)

    if args.push:
        git_commit_push(f"Publish note for {args.ticker}")

if __name__ == '__main__':
    main()
