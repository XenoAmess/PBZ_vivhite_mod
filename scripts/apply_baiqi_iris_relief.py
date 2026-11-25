"""Apply the five eye normals to copies of the published iris finish."""
import argparse
import json
from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from apply_baiqi_iris_roughness import FACE, STATES, pose_texture_selection
from fit_baiqi_cc0_wardrobe import rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--maps', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, maps, output = ((ROOT / p).resolve() for p in (args.source, args.source_inputs, args.maps, args.out))
    assert output != source and output.is_relative_to(ROOT)
    expected = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    inputs_map = json.loads((maps / 'iris_relief_inputs.json').read_text(encoding='utf-8'))
    normal_files = [maps / f'{state}_iris_normal.png' for state in STATES]
    assert all(fingerprint(path) == inputs_map['states'][state]['preview_sha256']
               for state, path in zip(STATES, normal_files, strict=True))
    output.mkdir(parents=True, exist_ok=True)
    record = {}
    for form in ('coat_on', 'coat_off'):
        path = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(path)
        assert source_hash == expected[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        body, head, armature = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature'))
        geometry = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH'}
        assert geometry[body] == expected[form]['body_sha256']
        rig = rest_signature(armature)
        material = head.data.materials[FACE]
        controller = bpy.data.objects['BaiQi Eye Preview']
        color = pose_texture_selection(material, controller, normal_files, 'Iris relief')
        tree = material.node_tree
        eye = tree.nodes['Principled BSDF'].inputs['Normal']
        assert not eye.is_linked
        normal = tree.nodes.new('ShaderNodeNormalMap')
        normal.label = 'Iris relief response'
        normal.uv_map = 'BaiQiCanvas'
        driver = normal.inputs['Strength'].driver_add('default_value').driver
        pose = driver.variables.new()
        pose.name = 'pose'
        pose.targets[0].id = controller
        pose.targets[0].data_path = '["pose"]'
        driver.expression = '0.0 if pose == 2 else 0.75'
        tree.links.new(color, normal.inputs['Color'])
        tree.links.new(normal.outputs['Normal'], eye)
        assert all(mesh_fingerprint(obj) == value for obj, value in geometry.items())
        assert rest_signature(armature) == rig
        target = output / path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        record[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(target),
                        'cc0_body_sha256': geometry[body], 'original_head_sha256': geometry[head]}
    (output / 'iris_relief.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
