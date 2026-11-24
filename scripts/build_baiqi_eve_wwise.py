"""Mount limbic7's local CombatOnly archive at independent BaiQi Wwise event paths."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
from zipfile import ZipFile


ARCHIVE_SHA256 = '4f28e147eae8022dbc27e769b0247de06f7233980c1716056e035369ebd48c03'
NAME = 'PBZOutfit_BaiQiEve_P'
ORIGINAL = '/Game/Wwise/Events/VO/Int/Hun/Battle/'
PRIVATE = '/Game/Wwise/Events/VO/Int/Eve/BaiQiX/'
CONTENT = Path('ProjectPBZ/Content/Wwise/Events/VO/Int')
CHINESE = 1016554174
HEADER = b'BKHD\x28\0\0\0'
RIFF = b'RIFF'
WORD = struct.Struct('<I')
OBJECT_HEADER = struct.Struct('<BII')


def extract_archive(archive, dest, game):
    digest = sha256(archive.read_bytes()).hexdigest()
    assert digest == ARCHIVE_SHA256, 'Select Nexus file 3368, version 1.3 CombatOnly.'
    dest.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive) as content:
        candidates = {Path(item.filename).suffix: item for item in content.infolist()
                      if not item.is_dir() and Path(item.filename).stem == 'zzzz_PBZ_HunFemale_Combat_P'}
        assert set(candidates) == {'.pak', '.ucas', '.utoc'}
        for suffix in ('.ucas', '.utoc'):
            (dest / ('source' + suffix)).write_bytes(content.read(candidates[suffix]))
    for name in ('global.ucas', 'global.utoc'):
        shutil.copyfile(game / 'ProjectPBZ/Content/Paks' / name, dest / name)


def bank_metadata(data):
    spans = []
    ids = set()
    chinese = None
    cursor = 0
    while cursor < len(data):
        assert data[cursor:cursor + len(HEADER)] == HEADER or data[cursor:cursor + 4] == RIFF, cursor
        if data[cursor:cursor + 4] == RIFF:
            assert data[cursor + 8:cursor + 12] == b'WAVE'
            cursor += 8 + WORD.unpack_from(data, cursor + 4)[0]
            continue
        bank = WORD.unpack_from(data, cursor + 12)[0]
        language = WORD.unpack_from(data, cursor + 16)[0]
        if language == CHINESE:
            chinese = bank
        ids.add(bank)
        start = cursor
        cursor += 8 + WORD.unpack_from(data, cursor + 4)[0]
        assert data[cursor:cursor + 4] == b'HIRC', cursor
        end = cursor + 8 + WORD.unpack_from(data, cursor + 4)[0]
        count = WORD.unpack_from(data, cursor + 8)[0]
        entry = cursor + 12
        for _ in range(count):
            kind, length, item = OBJECT_HEADER.unpack_from(data, entry)
            assert length >= 4 and entry + 5 + length <= end
            ids.add(item)
            if kind == 2:
                source, cache = struct.unpack_from('<II', data, entry + 14)
                ids.update((source, cache))
            entry += 5 + length
        assert entry == end
        spans.append((start, end))
        cursor = end
    assert cursor == len(data) and chinese and spans
    ids.discard(0)
    return chinese, ids, spans


def remap_file(source, target, identity, reserved):
    header = source.read_bytes()
    assert len(ORIGINAL) == len(PRIVATE)
    assert header.count(ORIGINAL.encode('ascii')) == 2
    target.write_bytes(header.replace(ORIGINAL.encode('ascii'), PRIVATE.encode('ascii')))
    bulk = source.with_suffix('.ubulk').read_bytes()
    event, ids, spans = bank_metadata(bulk)
    mapping = {}
    for value in sorted(ids):
        digest = sha256(f'pbz.baiqi.eve:{identity}:{value}'.encode('ascii')).digest()
        remapped = WORD.unpack_from(digest)[0]
        assert remapped not in reserved and remapped not in ids and remapped != 0
        reserved.add(remapped)
        mapping[WORD.pack(value)] = WORD.pack(remapped)
    pattern = re.compile(b'|'.join(re.escape(word) for word in mapping))
    replace = lambda block: pattern.sub(lambda match: mapping[match.group()], block)
    edited = bytearray(bulk)
    for a, b in spans:
        edited[a:b] = replace(bulk[a:b])
    export = source.with_suffix('.uexp').read_bytes()
    assert export.count(WORD.pack(event)) >= 2
    target.with_suffix('.uexp').write_bytes(replace(export))
    target.with_suffix('.ubulk').write_bytes(edited)
    new_id = WORD.unpack(mapping[WORD.pack(event)])[0]
    assert bank_metadata(edited)[0] == new_id
    assert len(edited) == len(bulk)
    for (_, end), (next_header, _) in zip(spans, spans[1:] + [(len(bulk), len(bulk))]):
        assert edited[end:next_header] == bulk[end:next_header]
    return new_id


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def build(args):
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    source = out / 'conversion_source'
    extract_archive(args.archive, source, args.game_root)
    retoc = args.retoc.resolve()
    legacy = out / 'legacy'
    run(retoc, 'to-legacy', source, legacy, '--version', 'UE5_7', '--no-shaders', '--filter', 'Hun/Battle/')
    owned = out / 'alias'
    dest = owned / CONTENT / 'Eve/BaiQiX'
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(legacy / 'scriptobjects.bin', owned / 'scriptobjects.bin')
    combat = legacy / CONTENT / 'Hun/Battle'
    inputs = sorted(combat.glob('*.uasset'), key=lambda p: p.name.lower())
    assert len(inputs) == 39 and set(legacy.rglob('*.uasset')) == set(inputs)
    routes = {}
    ids = set().union(*(bank_metadata(asset.with_suffix('.ubulk').read_bytes())[1] for asset in inputs))
    for asset in inputs:
        name = asset.stem
        assert re.fullmatch(r'[a-z0-9_]+', name.lower())
        event = remap_file(asset, dest / asset.name, name.lower(), ids)
        routes[name.lower()] = {'object': PRIVATE + name + '.' + name, 'id': event}
    target = out / 'install'
    target.mkdir(exist_ok=True)
    toc = target / (NAME + '.utoc')
    run(retoc, 'to-zen', owned, toc, '--version', 'UE5_7')
    listing = subprocess.check_output([str(retoc), 'list', '--path', str(toc)], encoding='utf-8')
    found = {word.removeprefix('../../../') for word in listing.split() if word.endswith('.uasset')}
    assert found == {(CONTENT / 'Eve/BaiQiX' / asset.name).as_posix() for asset in inputs}
    run(retoc, 'verify', toc)
    assert (target / (NAME + '.pak')).is_file()
    binding = target / 'eve-combat-data.js'
    binding.write_text('module.exports = ' + json.dumps(routes, indent=2) + ';\n', encoding='utf-8')
    manifest = {
        'status': 'readback_verified_pending_game', 'replacement_packages': [], 'events': len(routes),
        'donor_sha256': ARCHIVE_SHA256, 'routing_sha256': sha256(binding.read_bytes()).hexdigest(),
        'files': [{'name': path.name, 'bytes': path.stat().st_size, 'sha256': sha256(path.read_bytes()).hexdigest()}
                  for path in (target / (NAME + suffix) for suffix in ('.pak', '.utoc', '.ucas'))],
    }
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('BAIQI_EVE_WWISE_READY', target, len(routes))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--retoc', type=Path, required=True)
    parser.add_argument('--game-root', type=Path, default=Path(r'Z:\SteamLibrary\steamapps\common\PBZ'))
    parser.add_argument('--out', type=Path, default=Path('build/baiqi_eve_wwise'))
    build(parser.parse_args())
