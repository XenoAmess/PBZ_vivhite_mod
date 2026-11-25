"""Archive the two complete Blender forms, game inputs, and selected QA evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile


FORMS = ('coat_on', 'coat_off')
INPUT_FILES = {'form_inputs.json', 'engine_materials.json', 'surface_finish.json', 'surface_finish_readback.json',
               'eye_palette.json', 'iris_roughness.json', 'iris_relief_inputs.json'}
TEXTURE_DIRS = ('textures', 'baked', 'native_textures')


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version')
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--baked', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--eye-preview', type=Path)
    parser.add_argument('--evidence', type=Path, action='append', default=[])
    args = parser.parse_args()
    assert re.fullmatch(r'\d{3}', args.version) and re.fullmatch(r'[0-9a-f]{40}', args.source_commit)
    args.out.mkdir(parents=True, exist_ok=True)

    files = {f'blender/BaiQi_CC0_{form}.blend': args.models / f'BaiQi_CC0_{form}.blend' for form in FORMS}
    inputs = json.loads((args.baked / 'form_inputs.json').read_text(encoding='utf-8'))
    for form in FORMS:
        model = files[f'blender/BaiQi_CC0_{form}.blend']
        assert inputs[form]['source_sha256'] == sha256(model), model
        fbx = f'BaiQi_Adult_{form}.fbx'
        files[f'baked/{fbx}'] = args.baked / fbx
        inputs[form]['fbx'] = fbx
        if args.eye_preview:
            files[f'eye_preview/{model.name}'] = args.eye_preview / model.name
    for name in sorted(INPUT_FILES - {'form_inputs.json'}):
        if (args.baked / name).is_file():
            files[f'baked/{name}'] = args.baked / name
    for directory in TEXTURE_DIRS:
        for path in sorted((args.baked / directory).glob('*.png')):
            files[f'baked/{directory}/{path.name}'] = path
        for path in sorted((args.baked / directory).glob('*.jpg')):
            files[f'baked/{directory}/{path.name}'] = path
    for path in args.evidence:
        assert path.suffix.lower() in {'.json', '.md', '.jpg', '.png'}, path
        assert f'qa/{path.name}' not in files, path.name
        files[f'qa/{path.name}'] = path

    portable = (json.dumps(inputs, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    contents = {name: {'sha256': sha256(path), 'bytes': path.stat().st_size} for name, path in files.items()}
    contents['baked/form_inputs.json'] = {'sha256': hashlib.sha256(portable).hexdigest(), 'bytes': len(portable)}
    manifest = {'version': args.version, 'source_commit': args.source_commit, 'status': 'offline_candidate', 'files': contents}
    archive = args.out / f'BaiQi_{args.version}_Model_Archive.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as out:
        for name, path in files.items():
            out.write(path, name)
        out.writestr('baked/form_inputs.json', portable)
        out.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    with zipfile.ZipFile(archive) as check:
        assert check.testzip() is None
    print(f'{archive} {sha256(archive)}', flush=True)


if __name__ == '__main__':
    main()
