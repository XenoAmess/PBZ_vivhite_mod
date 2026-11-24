"""Verify the staged Adult Soul replacement from the mounted IO Store files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
GAME = Path(r'Z:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks')


def cooked_path(asset):
    mount, name = asset[1:].split('/', 1)
    return {'HuaShira': 'ProjectPBZ/Plugins/HuaShira/Content/',
            'Game': 'ProjectPBZ/Content/'}[mount] + name


def export(packages, destination, command, arguments, mounted=None):
    env = os.environ.copy()
    env['PBZX_AES'] = (TOOLS / '_private/aes.txt').read_text().strip()
    env.pop('PBZX_EXTRA', None)
    if mounted:
        env['PBZX_EXTRA'] = str(mounted)
    result = subprocess.run([str(TOOLS / 'PbzExport/PbzExport.exe'), str(packages), str(TOOLS / 'Mappings.usmap'),
                             str(TOOLS / 'oo2core_9_win64.dll'), str(destination), command, *arguments],
                            env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    (destination / f'{command}.log').write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
    assert result.returncode == 0 and 'FAIL ' not in result.stdout, (command, destination)
    return result.stdout


def verify_bones(rows, reference):
    original = {row['name']: row for row in reference}
    observed = {row['name']: row for row in rows}
    assert original.keys() <= observed.keys()
    errors = []
    for name, a in original.items():
        b = observed[name]
        expected_parent = reference[a['parent']]['name'] if a['parent'] >= 0 else None
        actual_parent = rows[b['parent']]['name'] if b['parent'] >= 0 else None
        assert expected_parent == actual_parent, name
        assert abs(abs(sum(x * y for x, y in zip(a['q'], b['q']))) - 1.) < .00002, name
        assert max(abs(x - y) for x, y in zip(a['s'], b['s'])) < .0003, name
        errors.append(max(abs(x - y) for x, y in zip(a['t'], b['t'])))
    assert max(errors) < .0003, max(errors)
    return max(errors)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('package', type=Path)
    parser.add_argument('allowlist', type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    allow = json.loads(args.allowlist.read_text(encoding='utf-8'))
    manifest = json.loads((package / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['source_sha256'] == allow['source_sha256'] and manifest['form'] == allow['form']
    destination = ROOT / 'artifacts/extracted' / ('baiqi_054_' + allow['form'])
    destination.mkdir(parents=True, exist_ok=True)
    listed = export(package, destination, 'list', ['.'])
    members = {line.strip().replace('\\', '/') for line in listed.splitlines() if '.uasset' in line.lower()}
    expected = {cooked_path(path) + '.uasset' for path in allow['replacement_packages'] + allow['owned_assets']}
    found = {name.lower() for name in members}
    required = {name.lower() for name in expected}
    assert found == required, {'missing': sorted(required - found), 'extra': sorted(found - required)}
    assert not any('young_hun' in path or 'hun_young' in path for path in found)
    assert not any(cooked_path(path).lower() + '.uasset' in found for path in allow['excluded_placeholders'])
    for entry in manifest['files']:
        with (package / entry['name']).open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == entry['sha256']
    bodies = [cooked_path(row['path']) for row in allow['staged_bodies']]
    export(GAME, destination, 'skel', bodies, package)
    export(GAME, destination, 'json', bodies, package)
    reference = json.loads((ROOT / 'repro/game_reference/adult_reference.skel.json').read_text())['bones']
    matrix = []
    for body, stage in zip(bodies, allow['staged_bodies']):
        data = json.loads((destination / f'{body}.{Path(body).name}.skel.json').read_text(encoding='utf-8'))
        assert len(data['bones']) == allow['combined_bones']
        error = verify_bones(data['bones'], reference)
        assert 'Hun_Skin_Skeleton' in data['skeleton']
        materials = data['materials']
        assert len(materials) == stage['slot_count']
        assert all(row['slot'].lower().replace('_', ' ').startswith('baiqi invisible driver section')
                   for row in materials[:18]), materials[:18]
        assert all('BaiQi054/Shared/Materials/' in row['mat'] for row in materials), materials
        payload = (destination / (body + '.json')).read_text(encoding='utf-8')
        assert 'ABP_AdultBaiQi' in payload and 'PH_BaiQiClothThighs' in payload, body
        matrix.append({'mesh': stage['path'], 'bones': len(data['bones']), 'original_bone_error_cm': error,
                       'material_slots': len(materials), 'lods': data['lods'], 'replacement_post_process': True, 'cloth': True})
    report = {'status': 'readback_verified_pending_game', 'runtime_tested': False,
              'source_sha256': allow['source_sha256'], 'form': allow['form'], 'members': sorted(members), 'body_checks': matrix}
    (package / 'readback.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    manifest.update(status=report['status'], readback_file='readback.json')
    (package / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('BAIQI_COOKED_READBACK_VERIFIED', allow['form'], len(members), len(matrix))


if __name__ == '__main__':
    main()
