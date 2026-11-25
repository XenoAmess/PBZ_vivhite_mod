"""Pack a localized crown shading correction without changing the hair geometry."""
import argparse
import json
from pathlib import Path
import sys

import bpy
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from baiqi_artwork_shadow import CROWN_RELIEF_PROPERTY, CROWN_RELIEF_STRENGTH
from blend_baiqi_hair_roots import CROWN
from export_baiqi_game_forms import first_texture, game_uv
from fit_baiqi_cc0_wardrobe import rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint
from match_baiqi_neck_normals import raster_triangle, save_bridge_map
from refine_baiqi_face_lighting import HEAD, fingerprint


MAP_SIZE = 1024


def corner_normals(mesh):
    return np.array([tuple(normal.vector) for normal in mesh.corner_normals])


def bake_relief(mesh, prior_positions, prior_normals):
    reference = mesh.copy()
    game_uv(reference)
    reference.calc_loop_triangles()
    reference.calc_tangents(uvmap=reference.uv_layers.active.name)
    positions = np.array([tuple(vertex.co) for vertex in reference.vertices])
    normal = corner_normals(reference)
    vertex_ids = np.array([loop.vertex_index for loop in reference.loops])
    moves = np.linalg.norm(positions - prior_positions, axis=1)[vertex_ids]
    scale = np.clip(moves / .014, 0., 1.)
    weight = (.74 * scale * scale * (3. - 2. * scale))[:, None]
    target = (1. - weight) * normal + weight * prior_normals
    target /= np.linalg.norm(target, axis=1, keepdims=True)

    # Retain the same quantized directions used in the comparison bake.
    mapped = mesh.copy()
    mapped.normals_split_custom_set(target.tolist())
    target = corner_normals(mapped)
    bpy.data.meshes.remove(mapped)

    tangent = np.array([tuple(loop.tangent) for loop in reference.loops])
    bitangent = np.cross(normal, tangent) * np.array([loop.bitangent_sign for loop in reference.loops])[:, None]
    direction = np.column_stack((np.sum(target * tangent, axis=1),
                                -np.sum(target * bitangent, axis=1),
                                 np.sum(target * normal, axis=1)))
    direction[np.linalg.norm(target - normal, axis=1) < .0003] = (0., 0., 1.)
    uv = np.array([tuple(point.vector) for point in reference.uv_layers.active.uv])
    vectors = np.zeros((MAP_SIZE, MAP_SIZE, 3), dtype=np.float32)
    vectors[..., 2] = 1.
    depth = np.full(vectors.shape[:2], -1., dtype=np.float32)
    for face in reference.loop_triangles:
        corners, vertices = list(face.loops), list(face.vertices)
        # At the shared front and back UVs, use the surface visible from the rear.
        raster_triangle(vectors, depth, uv[corners], -positions[vertices, 1], direction[corners])
    bpy.data.meshes.remove(reference)
    pixels = np.rint((vectors * .5 + .5) * 255).astype(np.uint8)
    # The measured response softens the steep patch with the opposite tangent tilt.
    pixels[..., :2] = 255 - pixels[..., :2]
    return pixels, {'projected_texels': int((depth > -1.).sum()),
                    'tilted_texels': int((np.linalg.norm(vectors[..., :2], axis=2) > .003).sum())}


def pack_blender_relief(crown, normal_map):
    material = crown.data.materials[0]
    tree = material.node_tree
    albedo = first_texture(material)
    surface = tree.nodes['Principled BSDF'].inputs['Normal']
    assert not surface.is_linked and albedo.inputs['Vector'].is_linked
    crown[CROWN_RELIEF_PROPERTY] = CROWN_RELIEF_STRENGTH

    normal_texture = tree.nodes.new('ShaderNodeTexImage')
    normal_texture.label = 'BaiQi crown shading correction'
    normal_texture.image = bpy.data.images.load(str(normal_map))
    normal_texture.image.colorspace_settings.name = 'Non-Color'
    normal_texture.image.pack()
    normal_texture.extension = albedo.extension
    tree.links.new(albedo.inputs['Vector'].links[0].from_socket, normal_texture.inputs['Vector'])

    mask = tree.nodes.new('ShaderNodeAttribute')
    mask.attribute_type = 'OBJECT'
    mask.attribute_name = CROWN_RELIEF_PROPERTY
    normal = tree.nodes.new('ShaderNodeNormalMap')
    normal.uv_map = 'BaiQiCanvas'
    tree.links.new(mask.outputs['Fac'], normal.inputs['Strength'])
    tree.links.new(normal_texture.outputs['Color'], normal.inputs['Color'])
    tree.links.new(normal.outputs['Normal'], surface)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shape-reference', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    before, source, inputs, output = ((ROOT / p).resolve() for p in
                                      (args.shape_reference, args.source, args.source_inputs, args.out))
    assert output not in {before, source} and output.is_relative_to(ROOT)
    manifest = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    native_map = output / 'T_BaiQiNative_CrownRelief.png'
    blender_map = output / 'crown_relief_blender.png'
    records = {}
    reference_pixels = None
    for form in ('coat_on', 'coat_off'):
        filename = f'BaiQi_CC0_{form}.blend'
        bpy.ops.wm.open_mainfile(filepath=str(before / filename))
        old = bpy.data.objects[CROWN].data
        original_order = [loop.vertex_index for loop in old.loops]
        positions = np.array([tuple(vertex.co) for vertex in old.vertices])
        normals = corner_normals(old)
        original_hash = fingerprint(before / filename)

        path = source / filename
        source_hash = fingerprint(path)
        assert source_hash == manifest[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        crown, body, head, rig = (bpy.data.objects[name] for name in (CROWN, 'Body', HEAD, 'Armature'))
        assert original_order == [loop.vertex_index for loop in crown.data.loops]
        protected = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH'}
        assert protected[body] == manifest[form]['body_sha256']
        bones = rest_signature(rig)
        native, metrics = bake_relief(crown.data, positions, normals)
        if reference_pixels is None:
            reference_pixels = native
            save_bridge_map(native_map, native)
            blender = native.copy()
            blender[..., 1] = 255 - blender[..., 1]
            save_bridge_map(blender_map, blender)
        else:
            assert np.array_equal(native, reference_pixels)
        pack_blender_relief(crown, blender_map)
        assert all(mesh_fingerprint(obj) == digest for obj, digest in protected.items())
        assert rest_signature(rig) == bones
        target = output / filename
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        records[form] = {'shape_reference_sha256': original_hash, 'source_sha256': source_hash,
                         'candidate_sha256': fingerprint(target), 'authored_head_sha256': protected[head],
                         'cc0_body_sha256': protected[body], 'normal_strength': CROWN_RELIEF_STRENGTH, **metrics}
    (output / 'crown_relief.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
