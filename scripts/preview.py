"""Sync or check the existing preview wrapper using only Python's standard library."""
import argparse
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/design/agent-inspector.fragment.html'
EXPORT = ROOT / 'frontend/preview/index.html'


class FrameParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.documents = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'iframe' and attrs.get('id') == 'codex-visualization':
            self.documents.append(attrs['data-srcdoc'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check without writing files')
    args = parser.parse_args()
    source = SOURCE.read_text(encoding='utf-8').strip()
    exported = EXPORT.read_text(encoding='utf-8')
    frame = FrameParser()
    frame.feed(exported)
    if len(frame.documents) != 1:
        raise ValueError('Expected exactly one preview frame')
    inner = frame.documents[0]
    embedded = re.search(r'<script id="range-sample-run" type="application/json">(.*?)</script>', source, re.S)
    if embedded is None or json.loads(embedded.group(1)) != json.loads((ROOT / 'shared/fixtures/demo-run.json').read_text()):
        raise ValueError('Source fixture differs from shared/fixtures/demo-run.json; update the embedded data first')
    if source not in inner:
        if args.check:
            raise ValueError('Preview is stale. Run: python3 scripts/preview.py')
        start = inner.index('<div id="range-agent-inspector">')
        ending = '\n</script>\n</div>'
        end = inner.index(ending, start) + len(ending)
        inner = inner[:start] + source + inner[end:]
        exported, count = re.subn(r'data-srcdoc="[^"]*"', lambda _: 'data-srcdoc="' + escape(inner, quote=True) + '"', exported, count=1)
        if count != 1:
            raise ValueError('Could not locate preview frame attribute')
        EXPORT.write_text(exported, encoding='utf-8')
        print('Updated frontend/preview/index.html')
    node = shutil.which('node')
    if node:
        for script in re.findall(r'<script>(.*?)</script>', source, re.S):
            subprocess.run([node, '--check'], input=script, text=True, check=True)
    else:
        print('NOTE: Node unavailable; JavaScript syntax check skipped')
    print('PASS: preview matches source and shared fixture')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
