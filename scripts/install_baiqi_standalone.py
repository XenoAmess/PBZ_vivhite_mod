"""Install the verified standalone appearance and its optional voice runtime."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

from readback_baiqi_standalone import FRAMEWORK, OUT, ROOT, load, save


FRAMEWORK_HASHES = {
    'pak': '6d2628937efe7110394ec6ed42cafe86c527866689a038f6f304e4732187b636',
    'ucas': '33eace4ee87aa2509843eb3bdb1299021130501708507e99676befc4591ad4eb',
    'utoc': 'dcc203373db8e3b621ef0ce343580e5e5e50c103312ad8dd096865a1a4824584',
}
LOADER = FRAMEWORK.parent / 'PBZModLoader-1.0.4-win64.zip'
LOADER_HASH = 'cc1a03bf02b8f90a2f82657ca6e0cdffcb6bf312ba2afca1dbbd80f2828a5673'
OLD = ROOT / 'output/live2d_delta/baiqi_054_wardrobe'
VOICE = ROOT / 'mods/baiqi-voice'
VOICE_PATH = 'ProjectPBZ/PBZModLoader/mods/baiqi-voice/'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_verified(path, expected):
    data = path.read_bytes()
    assert digest(data) == expected, path
    return data


def stop_if_game_open(game):
    command = ("@(Get-CimInstance Win32_Process -Filter \"Name='PBZ.exe'\" | "
               "Select-Object ExecutablePath) | ConvertTo-Json -Compress")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
    rows = json.loads(result.stdout or '[]')
    if isinstance(rows, dict):
        rows = [rows]
    assert not any(row.get('ExecutablePath') and Path(row['ExecutablePath']).resolve().is_relative_to(game)
                   for row in rows), 'The game is still running'


def runtime_files(manifest, use_voice):
    paks = 'ProjectPBZ/Content/Paks/~mods/'
    for item in manifest['files']:
        name = item['name']
        assert name in {f'PBZOutfit_BaiQi_P.{suffix}' for suffix in FRAMEWORK_HASHES}
        yield paks + name, read_verified(OUT / name, item['sha256'])
    for suffix, expected in FRAMEWORK_HASHES.items():
        name = 'PBZOutfitFramework_P.' + suffix
        yield paks + name, read_verified(FRAMEWORK / name, expected)
    if use_voice:
        read_verified(LOADER, LOADER_HASH)
        with zipfile.ZipFile(LOADER) as archive:
            for entry in archive.infolist():
                name = entry.filename
                if entry.is_dir():
                    continue
                if name == 'platform/steam/version.dll' or name.startswith((
                        'ProjectPBZ/PBZModLoader/', 'ProjectPBZ/Content/JavaScript/PBZModLoader/')):
                    yield name, archive.read(entry)
        for name in ('main.js', 'preview.js'):
            yield VOICE_PATH + name, (VOICE / name).read_bytes()


def install(game, use_voice=True, dry_run=False):
    assert (game / 'platform/steam/PBZ.exe').is_file() and (game / 'ProjectPBZ/Content/Paks').is_dir()
    manifest = load(OUT / 'manifest.json')
    assert load(OUT / 'readback.json')['files'] == manifest['files']
    assert manifest['status'] in {'readback_verified_pending_game', 'runtime_verified'}
    pending = []
    for relative, data in runtime_files(manifest, use_voice):
        target = (game / relative).resolve()
        assert target.is_relative_to(game) and target != game
        if target.exists():
            if target.name != 'mods.ini':
                assert digest(target.read_bytes()) == digest(data), f'Conflicting installed file {relative}'
        else:
            pending.append((target, data))
    previous = []
    for item in load(OLD / 'manifest.json')['files']:
        target = game / 'ProjectPBZ/Content/Paks/~mods' / item['name']
        if target.is_file():
            read_verified(target, item['sha256'])
            previous.append(target)
    if dry_run:
        print(f'BAIQI_INSTALL_READY {len(pending)} new files, {len(previous)} previous files to back up')
        return
    stop_if_game_open(game)
    backup = game / 'ProjectPBZ/Saved/BaiQiModBackups' / datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup.mkdir(parents=True)
    created, replaced = [], []
    try:
        for target, data in pending:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                created.append(target)
                stream.write(data)
            read_verified(target, digest(data))
        for current in previous:
            stored = backup / current.name
            current.replace(stored)
            replaced.append((stored, current))
    except BaseException:
        for stored, current in reversed(replaced):
            stored.replace(current)
        for target in reversed(created):
            target.unlink(missing_ok=True)
        raise
    receipt = dict(backup=str(backup), created=[path.relative_to(game).as_posix() for path in created],
                   previous=[path.name for path in previous], voice=use_voice, files=manifest['files'])
    save(backup / 'install_receipt.json', receipt)
    save(OUT / 'install_receipt.json', receipt)
    save(OUT / 'manifest.json', dict(manifest, installed=True))
    print(f'BAIQI_INSTALLED {len(created)} new files, {len(previous)} prior files backed up')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-root', type=Path, default=Path(r'Z:\SteamLibrary\steamapps\common\PBZ'))
    parser.add_argument('--appearance-only', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    install(args.game_root.resolve(), not args.appearance_only, args.dry_run)
