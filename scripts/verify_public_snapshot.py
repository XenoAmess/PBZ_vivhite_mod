"""Verify the declared publication files without exposing private contents."""
import hashlib,json,re,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];manifest=json.loads((ROOT/'repro/manifest.json').read_text(encoding='utf-8'));private=ROOT/'tools/_private/aes.txt';known=[]
if private.is_file():
    value=private.read_text(encoding='utf-8').strip();known.extend([value.encode(),value.lower().encode(),value.upper().encode()])
    try:known.append(bytes.fromhex(value.removeprefix('0x').removeprefix('0X')))
    except ValueError:pass
patterns=[re.compile(rb'gh[op]_[A-Za-z0-9]{30,}'),re.compile(rb'github_pat_[A-Za-z0-9_]{40,}'),re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----')]
def clean(data):return not any(secret and secret in data for secret in known) and not any(p.search(data) for p in patterns)
for row in manifest['files']:
    path=(ROOT/row['path']).resolve();assert path.is_relative_to(ROOT);data=path.read_bytes();assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],row['path'];assert len(data)<100*1024*1024,row['path'];assert clean(data),'Private content in '+row['path']
    if path.suffix.lower()=='.zip':
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():assert clean(z.read(name)),'Private content in archive '+row['path']
print('PUBLIC_SNAPSHOT_VERIFIED',len(manifest['files']),'files; hashes, file limits and private content checked')
