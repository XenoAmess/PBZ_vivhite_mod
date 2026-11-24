"""Scan the explicit publication set without printing secret contents."""
from pathlib import Path
import re,subprocess
ROOT=Path(__file__).resolve().parents[1]
paths=[ROOT/'README.md',ROOT/'source-lock.json']
for directory in ['qa','scripts','SOP']:
    paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
patterns=[re.compile(rb'gh[op]_[A-Za-z0-9]{30,}'),re.compile(rb'github_pat_[A-Za-z0-9_]{40,}'),
    re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----')]
private_key=ROOT/'tools/_private/aes.txt'
known=private_key.read_text(encoding='utf-8').strip().encode() if private_key.is_file() else None
failed=[]
for path in paths:
    if not path.is_file():continue
    data=path.read_bytes()
    if (known and known in data) or any(p.search(data) for p in patterns):failed.append(path.relative_to(ROOT).as_posix())
if failed:raise SystemExit('Publication scan failed in: '+', '.join(failed))
print('PUBLIC_SOURCE_SCAN_CLEAN',len(paths),'files; known local key and credential signatures checked')
