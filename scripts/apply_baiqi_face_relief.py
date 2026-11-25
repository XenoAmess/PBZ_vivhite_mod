"""Apply a skin-lighting preview or update the existing relief texture."""
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
NECK = 'BaiQi neck junction shading'


def lit_mix(material):
    return next(node for node in material.node_tree.nodes if node.label == 'Skin finish')


def attach_normal(face, path, strength):
    tree = face.node_tree
    albedo = tree.nodes['Image Texture']
    vector = albedo.inputs['Vector'].links[0].from_socket
    texture = tree.nodes.new('ShaderNodeTexImage')
    texture.label = 'Local skin relief'
    texture.extension = 'EXTEND'
    texture.image = bpy.data.images.load(str(path))
    texture.image.colorspace_settings.name = 'Non-Color'
    texture.image.pack()
    tree.links.new(vector, texture.inputs['Vector'])
    tangent = tree.nodes.new('ShaderNodeNormalMap')
    tangent.label = 'Local skin relief response'
    tangent.uv_map = 'BaiQiCanvas'
    tangent.inputs['Strength'].default_value = strength
    tree.links.new(texture.outputs['Color'], tangent.inputs['Color'])
    diffuse = lit_mix(face).inputs[2].links[0].from_node
    assert diffuse.type == 'BSDF_DIFFUSE'
    tree.links.new(tangent.outputs['Normal'], diffuse.inputs['Normal'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--maps', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--replace-existing', action='store_true', help='Keep the existing material and update only its normal map.')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, maps, output = ((ROOT / value).resolve()
                                   for value in (args.source, args.source_inputs, args.maps, args.out))
    assert output != source and output.is_relative_to(ROOT)
    output.mkdir(parents=True, exist_ok=True)
    expected = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    design = json.loads((maps / 'face_relief_inputs.json').read_text(encoding='utf-8'))
    normal = maps / 'face_relief_blender.png'
    assert fingerprint(normal) == design['blender_normal_sha256']
    records = {}
    for form in ('coat_on', 'coat_off'):
        path = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(path)
        assert source_hash == expected[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        body, head, rig = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature'))
        meshes = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH'}
        assert meshes[body] == expected[form]['body_sha256']
        skeleton = rest_signature(rig)
        face, neck = (head.data.materials[name] for name in (FACE, NECK))
        artwork = {node.image: bytes(node.image.packed_file.data) for node in face.node_tree.nodes
                   if node.type == 'TEX_IMAGE' and node.image and node.image.packed_file}
        if args.replace_existing:
            tree = face.node_tree
            texture = next(node for node in tree.nodes if node.label == 'Local skin relief')
            strength = next(node for node in tree.nodes if node.label == 'Local skin relief response').inputs['Strength']
            assert abs(strength.default_value - design['normal_strength']) < 1e-6
            replacement = bpy.data.images.load(str(normal))
            replacement.colorspace_settings.name = texture.image.colorspace_settings.name
            assert tuple(replacement.size) == tuple(texture.image.size)
            replacement.pack()
            texture.image = replacement
        else:
            lit_mix(face).inputs[0].default_value = .65
            lit_mix(neck).inputs[0].default_value = .60
            attach_normal(face, normal, design['normal_strength'])
        assert all(mesh_fingerprint(obj) == value for obj, value in meshes.items())
        assert all(bytes(image.packed_file.data) == payload for image, payload in artwork.items())
        assert rest_signature(rig) == skeleton
        target = output / path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        records[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(target),
                         'cc0_body_sha256': meshes[body], 'original_head_sha256': meshes[head],
                         'blender_face_diffuse_fraction': round(lit_mix(face).inputs[0].default_value, 4),
                         'blender_neck_diffuse_fraction': round(lit_mix(neck).inputs[0].default_value, 4),
                         'nasal_strength': design.get('nasal_strength', 1.)}
    (output / 'face_relief.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
