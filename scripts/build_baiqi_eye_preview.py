"""Pack testable original eye states in standalone copies of the fitting files."""
import argparse
from pathlib import Path
import sys

import bpy

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'scripts'))
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--poses', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
source, states, output = ((root / path).resolve() for path in (args.source, args.poses, args.out))
assert output != source and output != states and output.is_relative_to(root)
output.mkdir(parents=True, exist_ok=True)
names = ('half_blink', 'closed', 'look_left', 'look_right')


def load_texture(tree, reference, state, suffix=''):
    node = tree.nodes.new('ShaderNodeTexImage')
    node.label = state + suffix
    node.image = bpy.data.images.load(str(states / (state + suffix + '.png')))
    node.image.colorspace_settings.name = reference.image.colorspace_settings.name
    node.image.pack()
    node.extension = reference.extension
    node.interpolation = reference.interpolation
    tree.links.new(reference.inputs['Vector'].links[0].from_socket, node.inputs['Vector'])
    return node


def connect_selection(tree, control, initial, alternates):
    targets = [link.to_socket for link in initial.links]
    current = initial
    for index, alternate in enumerate(alternates, start=1):
        mix = tree.nodes.new('ShaderNodeMixRGB')
        mix.label = 'Eye pose ' + names[index - 1]
        curve = mix.inputs[0].driver_add('default_value')
        variable = curve.driver.variables.new()
        variable.name = 'pose'
        variable.targets[0].id = control
        variable.targets[0].data_path = '["pose"]'
        curve.driver.expression = f'1 if pose == {index} else 0'
        tree.links.new(current, mix.inputs[1])
        tree.links.new(alternate, mix.inputs[2])
        current = mix.outputs[0]
    for target in targets:
        tree.links.new(current, target)


for form in ('coat_on', 'coat_off'):
    path = source / f'BaiQi_CC0_{form}.blend'
    bpy.ops.wm.open_mainfile(filepath=str(path))
    rig, head, body = (bpy.data.objects[name] for name in ('Armature', HEAD, 'Body'))
    before = mesh_fingerprint(body), mesh_fingerprint(head)
    control = bpy.data.objects.new('BaiQi Eye Preview', None)
    bpy.context.scene.collection.objects.link(control)
    control.parent = rig
    control.hide_render = True
    control.empty_display_size = .032
    control.location = (.28, 0, 1.49)
    control['pose'] = 0
    control.id_properties_ui('pose').update(min=0, max=4,
        description='0 neutral, 1 half blink, 2 closed, 3 look left, 4 look right')
    tree = head.data.materials['BaiQi original face appearance'].node_tree
    atlas = tree.nodes['Image Texture']
    feature = next(node for node in tree.nodes if node.label == 'Keep original facial artwork')
    textures = [load_texture(tree, atlas, name) for name in names]
    masks = [load_texture(tree, feature, name, '_mask') for name in names]
    connect_selection(tree, control, atlas.outputs['Color'], [node.outputs['Color'] for node in textures])
    connect_selection(tree, control, atlas.outputs['Alpha'], [node.outputs['Alpha'] for node in textures])
    connect_selection(tree, control, feature.outputs['Color'], [node.outputs['Color'] for node in masks])
    assert before == (mesh_fingerprint(body), mesh_fingerprint(head))
    bpy.ops.wm.save_as_mainfile(filepath=str(output / path.name))
