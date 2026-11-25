"""Give the iris its own pose-aware roughness while preserving the face artwork."""
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


FACE = 'BaiQi original face appearance'
STATES = ('neutral', 'half_blink', 'closed', 'look_left', 'look_right')


def pose_texture_selection(material, controller, images, label):
    tree = material.node_tree
    atlas = tree.nodes['Image Texture']
    coords = atlas.inputs['Vector'].links[0].from_socket
    maps = []
    for state, image in zip(STATES, images, strict=True):
        texture = tree.nodes.new('ShaderNodeTexImage')
        texture.label = label + ' ' + state
        texture.extension = 'EXTEND'
        texture.image = bpy.data.images.load(str(image))
        texture.image.colorspace_settings.name = 'Non-Color'
        texture.image.pack()
        tree.links.new(coords, texture.inputs['Vector'])
        maps.append(texture.outputs['Color'])
    coverage = maps[0]
    for index, mask in enumerate(maps[1:], start=1):
        selector = tree.nodes.new('ShaderNodeMixRGB')
        selector.label = label + ' pose ' + STATES[index]
        driver = selector.inputs[0].driver_add('default_value').driver
        value = driver.variables.new()
        value.name = 'pose'
        value.targets[0].id = controller
        value.targets[0].data_path = '["pose"]'
        driver.expression = f'1 if pose == {index} else 0'
        tree.links.new(coverage, selector.inputs[1])
        tree.links.new(mask, selector.inputs[2])
        coverage = selector.outputs['Color']
    return coverage


def add_iris_layer(material, controller, poses, roughness):
    tree = material.node_tree
    coverage = pose_texture_selection(material, controller, [poses / f'{state}_iris.png' for state in STATES],
                                      'Iris coverage')
    surface = tree.nodes['Principled BSDF'].inputs['Roughness']
    assert not surface.is_linked
    baseline = surface.default_value
    finish = tree.nodes.new('ShaderNodeMixRGB')
    finish.label = 'Iris roughness'
    tree.links.new(coverage, finish.inputs[0])
    finish.inputs[1].default_value = (baseline, baseline, baseline, 1.)
    finish.inputs[2].default_value = (roughness, roughness, roughness, 1.)
    tree.links.new(finish.outputs['Color'], surface)
    return baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--poses', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--roughness', type=float, default=.37)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, poses, output = ((ROOT / p).resolve() for p in (args.source, args.source_inputs, args.poses, args.out))
    assert source != output and output.is_relative_to(ROOT) and .25 <= args.roughness <= .56
    expected = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    report = {}
    for form in ('coat_on', 'coat_off'):
        file = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(file)
        assert source_hash == expected[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(file))
        body, head, armature = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature'))
        geometry = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH'}
        assert geometry[body] == expected[form]['body_sha256']
        skeleton = rest_signature(armature)
        controller = bpy.data.objects['BaiQi Eye Preview']
        assert controller['pose'] == 0
        baseline = add_iris_layer(head.data.materials[FACE], controller, poses, args.roughness)
        assert geometry == {obj: mesh_fingerprint(obj) for obj in geometry}
        assert skeleton == rest_signature(armature)
        destination = output / file.name
        bpy.ops.wm.save_as_mainfile(filepath=str(destination))
        report[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(destination),
                        'cc0_body_sha256': geometry[body], 'original_head_sha256': geometry[head],
                        'baseline_roughness': baseline, 'iris_roughness': args.roughness}
    (output / 'iris_finish.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
