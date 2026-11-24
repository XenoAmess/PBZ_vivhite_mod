"""Read-only AES constant scan, signatures from GHFear/AESDumpster.

Only writes candidates to the project's private tools directory. Does not patch
or run the game. A candidate must be checked against the real archive index.
"""
import json
import math
import mmap
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'vendor/AESDumpster/AESDumpster/AESDumpster/KeyTools/KeyDumpster.h'
text = HEADER.read_text()
patterns_block = text.split('m_keyPatterns = {')[1].split('};')[0]
patterns = re.findall(r'"([C0-9A-F? ]+)"', patterns_block)
offsets = [[3, 10, 17, 24, 35, 42, 49, 56], [2, 9, 16, 23, 30, 37, 44, 51],
           [3, 10, 21, 28, 35, 42, 49, 56], [51, 45, 38, 31, 24, 17, 10, 3]]
false_block = text.split('m_falsePositives = {')[1].split('};')[0]
false_keys = set(re.findall(r'"([0-9A-F]+)"', false_block))
candidates = {}
exe = Path(r'Z:\SteamLibrary\steamapps\common\PBZ\platform\steam\PBZ.exe')
with exe.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
    for i, pattern in enumerate(patterns):
        rx = b''.join(b'.' if token == '?' else re.escape(bytes.fromhex(token)) for token in pattern.split())
        for match in re.finditer(rx, data, flags=re.DOTALL):
            key = b''.join(data[match.start()+n:match.start()+n+4] for n in offsets[i]).hex().upper()
            frequency = Counter(key)
            entropy = -sum(n/len(key)*math.log2(n/len(key)) for n in frequency.values())
            if entropy >= 3.3 and key not in false_keys:
                candidates[key] = {'file_offset': match.start(), 'pattern': i, 'entropy': entropy}
out = ROOT / 'tools/_private'
out.mkdir(parents=True, exist_ok=True)
(out / 'aes_candidates.json').write_text(json.dumps(candidates, indent=2))
print(f'Scanned {exe.stat().st_size} bytes; {len(candidates)} candidates. Values stored privately.')
