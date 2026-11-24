"""Install the locally built EVE bank on top of the BaiQi 054 standalone appearance."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from tempfile import NamedTemporaryFile


HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent / 'mods/baiqi-voice'
CONTAINER = 'PBZOutfit_BaiQiEve_P'


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix='baiqi-', delete=False) as stream:
        temp = Path(stream.name)
        stream.write(data)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def game_is_running(game):
    command = ("@(Get-CimInstance Win32_Process -Filter \"Name='PBZ.exe'\" | "
               "Select-Object ExecutablePath) | ConvertTo-Json -Compress")
    result = subprocess.check_output(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                                     encoding='utf-8', errors='replace')
    items = json.loads(result or '[]')
    items = [items] if isinstance(items, dict) else items
    return any(row.get('ExecutablePath') and Path(row['ExecutablePath']).resolve().is_relative_to(game)
               for row in items)


def install(args):
    game = args.game_root.resolve()
    bank = args.bank.resolve()
    manifest = json.loads((bank / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['status'] in {'readback_verified_pending_game', 'runtime_verified'}
    assert manifest['events'] == 39 and not manifest['replacement_packages']
    paks = (game / 'ProjectPBZ/Content/Paks/~mods').resolve()
    runtime = (game / 'ProjectPBZ/PBZModLoader/mods/baiqi-voice').resolve()
    assert paks.is_relative_to(game) and runtime.is_relative_to(game)
    assert (paks / 'PBZOutfit_BaiQi_P.utoc').is_file() and (runtime / 'preview.js').is_file(), 'Install BaiQi 054 first.'
    assert (game / 'platform/steam/PBZ.exe').is_file(), game
    assert not any(paks.rglob('zzzz_PBZ_HunFemale_Combat_P.utoc')), 'The original global voice pack is active.'
    destinations = {}
    for row in manifest['files']:
        path = paks / row['name']
        assert path.name in {CONTAINER + suffix for suffix in ('.pak', '.ucas', '.utoc')}
        data = (bank / path.name).read_bytes()
        assert sha256(data).hexdigest() == row['sha256'], path.name
        destinations[path] = data
    assert len(destinations) == 3
    route_path = runtime / 'eve-combat-data.js'
    data = (bank / route_path.name).read_bytes()
    assert sha256(data).hexdigest() == manifest['routing_sha256']
    destinations[route_path] = data
    destinations[runtime / 'main.js'] = (RUNTIME / 'main.js').read_bytes()
    if args.dry_run:
        print('BAIQI_EVE_INSTALL_READY', len(destinations))
        return
    assert not game_is_running(game), 'Close Phantom Blade Zero before installing the EVE audio bank.'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = (game / 'ProjectPBZ/Saved/BaiQiModBackups' / ('eve_' + stamp)).resolve()
    assert backup.is_relative_to(game)
    written = {}
    try:
        for path, data in destinations.items():
            assert path.resolve().is_relative_to(game)
            old = path.read_bytes() if path.exists() else None
            if old == data:
                continue
            if old is not None:
                atomic_write(backup / path.relative_to(game), old)
            atomic_write(path, data)
            written[path] = old
            assert path.read_bytes() == data, path
    except BaseException:
        for path, old in reversed(list(written.items())):
            if old is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, old)
        raise
    print('BAIQI_EVE_INSTALLED', len(written), backup)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-root', type=Path, default=Path(r'Z:\SteamLibrary\steamapps\common\PBZ'))
    parser.add_argument('--bank', type=Path, default=Path('build/baiqi_eve_wwise/install'))
    parser.add_argument('--dry-run', action='store_true')
    install(parser.parse_args())
