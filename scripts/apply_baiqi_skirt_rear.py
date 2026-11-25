"""Map the existing rear skirt faces to their gold border on the shared atlas."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fit_baiqi_cc0_wardrobe import rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint


FRONT = 'BaiQi pleated skirt artwork'
REAR = 'BaiQi white rear skirt'
REAR_ATLAS = 'baiqi_skirt_rear_atlas'


def map_rear(mesh, texture, design):
    front, rear = tuple(mesh.materials)
    assert (front.name, rear.name) == (FRONT, REAR)
    layer = mesh.uv_layers.active
    width, height = texture.size
    left, top, right, bottom = design['atlas_box']
    first_row, last_row = design['source_rows']
    mapped = 0
    for face in mesh.polygons:
        if face.material_index != 1:
            continue
        for index in face.loop_indices:
            point = mesh.vertices[mesh.loops[index].vertex_index].co
            azimuth = math.atan2(point.x, point.y - .015) % math.tau
            u = min(1., max(0., (azimuth - math.pi / 2.) / math.pi))
            source_row = (1. - layer.uv[index].vector.y) * height
            v = (source_row - first_row) / (last_row - first_row)
            assert 0. <= v <= 1.
            layer.uv[index].vector = ((left + .5 + u * (right - left - 1)) / width,
                                      1. - (top + .5 + v * (bottom - top - 1)) / height)
            mapped += 1
    assert mapped > 0
    front.node_tree.nodes['Image Texture'].image = texture
    front[REAR_ATLAS] = True
    tree = rear.node_tree
    color = tree.nodes['Principled BSDF'].inputs['Base Color']
    assert not color.is_linked
    coordinates = tree.nodes.new('ShaderNodeUVMap')
    coordinates.uv_map = layer.name
    atlas = tree.nodes.new('ShaderNodeTexImage')
    atlas.image = texture
    tree.links.new(coordinates.outputs['UV'], atlas.inputs['Vector'])
    tree.links.new(atlas.outputs['Color'], color)
    return mapped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--maps', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, maps, out = ((ROOT / p).resolve() for p in (args.source, args.source_inputs, args.maps, args.out))
    assert source != out and out.is_relative_to(ROOT)
    manifest = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    design = json.loads((maps / 'skirt_rear.json').read_text(encoding='utf-8'))
    path = maps / 'skirt_rear.png'
    assert fingerprint(path) == design['candidate_sha256']
    out.mkdir(parents=True, exist_ok=True)
    forms = {}
    for form in ('coat_on', 'coat_off'):
        old = source / f'BaiQi_CC0_{form}.blend'
        assert fingerprint(old) == manifest[form]['source_sha256']
        assert design['source_sha256'] == manifest[form]['materials'][FRONT]['images'][0]['sha256']
        bpy.ops.wm.open_mainfile(filepath=str(old))
        body, head, armature, skirt = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature', 'BaiQi pleated skirt'))
        fixed = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj != skirt}
        assert fixed[body] == manifest[form]['body_sha256']
        rig = rest_signature(armature)
        texture = bpy.data.images.load(str(path))
        texture.pack()
        loops = map_rear(skirt.data, texture, design)
        assert all(mesh_fingerprint(obj) == value for obj, value in fixed.items())
        assert rig == rest_signature(armature)
        target = out / old.name
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        forms[form] = {'candidate_sha256': fingerprint(target), 'cc0_body_sha256': fixed[body],
                       'original_head_sha256': fixed[head], 'rear_uv_loops': loops}
    (out / 'skirt_rear.json').write_text(json.dumps(forms, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
