"""Select graduated native neck pigment on the archived fitting copies."""
import argparse
import json
from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fit_baiqi_cc0_wardrobe import rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint


NECK = 'BaiQi neck junction shading'
NECK_MARKER = 'baiqi_native_neck_pigment'
LOW_Z, HIGH_Z = 1.315, 1.365


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, output = ((ROOT / path).resolve() for path in (args.source, args.source_inputs, args.out))
    assert output != source and output.is_relative_to(ROOT)
    expected = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    report = {}
    for form in ('coat_on', 'coat_off'):
        name = f'BaiQi_CC0_{form}.blend'
        path = source / name
        source_hash = fingerprint(path)
        assert source_hash == expected[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        head, body, rig = (bpy.data.objects[key] for key in (HEAD, 'Body', 'Armature'))
        hashes = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH'}
        assert hashes[body] == expected[form]['body_sha256']
        skeleton = rest_signature(rig)
        neck = head.data.materials[NECK]
        neck[NECK_MARKER] = True
        assert all(mesh_fingerprint(obj) == value for obj, value in hashes.items())
        assert rest_signature(rig) == skeleton
        destination = output / name
        bpy.ops.wm.save_as_mainfile(filepath=str(destination))
        report[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(destination),
                        'cc0_body_sha256': hashes[body], 'original_head_sha256': hashes[head],
                        'native_neck_uv_range_m': [LOW_Z, HIGH_Z]}
    (output / 'neck_pigment.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
