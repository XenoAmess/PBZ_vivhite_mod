"""Add the original fringe's light response to the two BaiQi fitting forms."""
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


FRINGE = 'BaiQi bob front appearance'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--maps', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, maps, output = ((ROOT / path).resolve() for path in (args.source, args.source_inputs, args.maps, args.out))
    assert output != source and output.is_relative_to(ROOT)
    manifest = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    design = json.loads((maps / 'fringe_relief_inputs.json').read_text(encoding='utf-8'))
    normal = maps / 'fringe_relief_blender.png'
    assert fingerprint(normal) == design['blender_sha256']
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    for form in ('coat_on', 'coat_off'):
        path = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(path)
        assert source_hash == manifest[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        body, head, rig = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature'))
        meshes = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH'}
        assert meshes[body] == manifest[form]['body_sha256']
        skeleton = rest_signature(rig)
        tree = bpy.data.materials[FRINGE].node_tree
        albedo = tree.nodes['Image Texture']
        surface = tree.nodes['Principled BSDF'].inputs['Normal']
        assert not surface.is_linked
        assert design['source_sha256'] == manifest[form]['materials'][FRINGE]['images'][0]['sha256']
        texture = tree.nodes.new('ShaderNodeTexImage')
        texture.label = 'Original fringe clump relief'
        texture.image = bpy.data.images.load(str(normal))
        texture.image.colorspace_settings.name = 'Non-Color'
        texture.image.pack()
        texture.extension = albedo.extension
        tree.links.new(albedo.inputs['Vector'].links[0].from_socket, texture.inputs['Vector'])
        tangent = tree.nodes.new('ShaderNodeNormalMap')
        tangent.label = 'Original fringe light response'
        tangent.uv_map = 'BaiQiCanvas'
        tangent.inputs['Strength'].default_value = design['normal_strength']
        tree.links.new(texture.outputs['Color'], tangent.inputs['Color'])
        tree.links.new(tangent.outputs['Normal'], surface)
        assert all(mesh_fingerprint(obj) == digest for obj, digest in meshes.items())
        assert rest_signature(rig) == skeleton
        destination = output / path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(destination))
        records[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(destination),
                         'cc0_body_sha256': meshes[body], 'original_head_sha256': meshes[head]}
    (output / 'fringe_relief.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
