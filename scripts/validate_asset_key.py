"""Validate local AES candidates against the actual game's pak index SHA1."""
import hashlib
import json
import struct
from pathlib import Path
from Cryptodome.Cipher import AES

ROOT = Path(__file__).resolve().parents[1]
pak = Path(r'Z:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks\ProjectPBZ-Windows.pak')
with pak.open('rb') as f:
    f.seek(-4096, 2)
    footer = f.read()
    magic = footer.rfind(b'\xe1\x12\x6f\x5a')
    assert magic >= 0, 'PakInfo magic not found'
    version, offset, size = struct.unpack_from('<iqq', footer, magic + 4)
    index_hash = footer[magic+24:magic+44]
    f.seek(offset)
    encrypted = f.read(size)
candidates = json.loads((ROOT / 'tools/_private/aes_candidates.json').read_text())
valid = []
for key in candidates:
    plain = AES.new(bytes.fromhex(key), AES.MODE_ECB).decrypt(encrypted)
    if hashlib.sha1(plain).digest() == index_hash:
        valid.append(key)
assert len(valid) == 1, f'Expected one hash-verified key, got {len(valid)}'
(ROOT / 'tools/_private/aes.txt').write_text(valid[0])
report = {'pak_version': version, 'index_offset': offset, 'index_size': size,
          'index_sha1': index_hash.hex(), 'candidate_count': len(candidates),
          'verified_keys': len(valid), 'game_executable_modified': False}
(ROOT / 'artifacts/key_verification.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report))
