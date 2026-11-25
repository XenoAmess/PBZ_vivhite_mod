"""Soften the gold eyewear reflection while preserving its geometry and colors."""
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


FRAME_MATERIAL = 'BaiQi round gold glasses appearance'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--roughness', type=float, default=.46)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, output = ((ROOT / p).resolve() for p in (args.source, args.source_inputs, args.out))
    assert source != output and output.is_relative_to(ROOT)
    assert .36 <= args.roughness <= .58
    expected = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    report = {}
    for form in ('coat_on', 'coat_off'):
        source_path = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(source_path)
        assert source_hash == expected[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(source_path))
        body, head, rig = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature'))
        geometry = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH'}
        skeleton = rest_signature(rig)
        assert geometry[body] == expected[form]['body_sha256']
        frame = bpy.data.materials[FRAME_MATERIAL].node_tree.nodes['Principled BSDF']
        assert not frame.inputs['Roughness'].is_linked and not frame.inputs['Metallic'].is_linked
        previous = frame.inputs['Roughness'].default_value
        metal = frame.inputs['Metallic'].default_value
        assert abs(previous - .36) < 1e-6 and abs(metal - .62) < 1e-6
        frame.inputs['Roughness'].default_value = args.roughness
        assert all(mesh_fingerprint(obj) == value for obj, value in geometry.items())
        assert rest_signature(rig) == skeleton
        destination = output / source_path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(destination))
        report[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(destination),
                        'cc0_body_sha256': geometry[body], 'original_head_sha256': geometry[head],
                        'frame_roughness': args.roughness, 'frame_metallic': metal}
    (output / 'frame_finish.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
