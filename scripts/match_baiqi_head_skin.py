"""Match visible BaiQi skin to a representative point on the original CC0 arms."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lock_baiqi_cc0_body import mesh_fingerprint


def arm_swatch(body):
    mesh = body.data
    mesh.calc_loop_triangles()
    skin = next(material for material in mesh.materials if material.name.endswith('_SKIN'))
    skin_slot = mesh.materials.find(skin.name)
    triangles = [triangle for triangle in mesh.loop_triangles if triangle.material_index == skin_slot]
    coordinates = [body.matrix_world @ vertex.co for vertex in mesh.vertices]
    tree = BVHTree.FromPolygons(coordinates, [triangle.vertices[:] for triangle in triangles], all_triangles=True)
    uv_layer = mesh.uv_layers.active.uv
    image = next(node.image for node in skin.node_tree.nodes if node.type == 'TEX_IMAGE')
    samples = []
    for side in (-1, 1):
        for radius in (.192, .212, .236, .260, .282):
            hit, _, index, _ = tree.ray_cast(Vector((side * radius, .15, 1.260)), Vector((0, -1, 0)), .22)
            if hit is None:
                continue
            triangle = triangles[index]
            weights = barycentric_transform(hit, *(coordinates[i] for i in triangle.vertices),
                                             Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
            uv = sum((fraction * uv_layer[loop].vector for fraction, loop in zip(weights, triangle.loops)), Vector((0, 0)))
            x = int(uv.x * image.size[0])
            y = int(uv.y * image.size[1])
            offset = 4 * (y * image.size[0] + x)
            samples.append((uv, np.array(image.pixels[offset:offset+3])))
    assert len(samples) >= 8, len(samples)
    median = np.median([rgb for _, rgb in samples], axis=0)
    uv, rgb = min(samples, key=lambda sample: np.linalg.norm(sample[1] - median))
    return image, uv, rgb, len(samples)


def swatch(node_tree, image, uv, name):
    texture = node_tree.nodes.new('ShaderNodeTexImage')
    texture.label = name
    texture.image = image
    point = node_tree.nodes.new('ShaderNodeCombineXYZ')
    point.inputs['X'].default_value = uv[0]
    point.inputs['Y'].default_value = uv[1]
    node_tree.links.new(point.outputs['Vector'], texture.inputs['Vector'])
    return texture.outputs['Color']


def expanded_holdout(mask_path, width, height):
    original = bpy.data.images.load(str(mask_path), check_existing=True)
    original.colorspace_settings.name = 'Non-Color'
    tw, th = original.size
    assert width % tw == 0 and height % th == 0, (tw, th, width, height)
    values = np.empty(tw * th * 4, dtype=np.float32)
    original.pixels.foreach_get(values)
    repeated = np.tile(values.reshape(th, tw, 4), (height // th, width // tw, 1))
    mask = bpy.data.images.new('BaiQi unchanged eye artwork mask', width=width, height=height)
    mask.colorspace_settings.name = 'Non-Color'
    mask.pixels.foreach_set(repeated.ravel())
    mask.pack()
    return mask


def face_material(material, body_image, body_uv, mask_path, meta):
    tree = material.node_tree
    nodes, links = tree.nodes, tree.links
    atlas = next(node for node in nodes if node.type == 'TEX_IMAGE')
    painted = nodes['Principled BSDF'].inputs['Base Color'].links[0].from_socket
    terminal = nodes['Material Output'].inputs['Surface']
    original = terminal.links[0].from_socket

    holdout = nodes.new('ShaderNodeTexImage')
    holdout.label = 'Keep original facial artwork'
    holdout.image = expanded_holdout(mask_path, *atlas.image.size)
    holdout.extension = 'CLIP'
    links.new(atlas.inputs['Vector'].links[0].from_socket, holdout.inputs['Vector'])
    body_color = swatch(tree, body_image, body_uv, 'Pigment sampled from CC0 upper arm')
    tiled_uv = [meta['flat_skin_swatch_uv'][0] * meta['tile_size'][0] / atlas.image.size[0],
                1 - (1 - meta['flat_skin_swatch_uv'][1]) * meta['tile_size'][1] / atlas.image.size[1]]
    source_color = swatch(tree, atlas.image, tiled_uv, 'Original flat face pigment')
    ratio = nodes.new('ShaderNodeVectorMath')
    ratio.operation = 'DIVIDE'
    links.new(body_color, ratio.inputs[0])
    links.new(source_color, ratio.inputs[1])
    pigment = nodes.new('ShaderNodeVectorMath')
    pigment.operation = 'MULTIPLY'
    links.new(painted, pigment.inputs[0])
    links.new(ratio.outputs['Vector'], pigment.inputs[1])
    facing = nodes.new('ShaderNodeLayerWeight')
    contour = nodes.new('ShaderNodeMapRange')
    links.new(facing.outputs['Facing'], contour.inputs['Value'])
    contour.inputs['To Min'].default_value = 1.
    contour.inputs['To Max'].default_value = .865
    shaded = nodes.new('ShaderNodeVectorMath')
    shaded.operation = 'SCALE'
    links.new(pigment.outputs['Vector'], shaded.inputs[0])
    links.new(contour.outputs[0], shaded.inputs['Scale'])
    flat = nodes.new('ShaderNodeEmission')
    flat.label = 'Shared arm pigment with the original colored lines and soft contour shading'
    links.new(shaded.outputs['Vector'], flat.inputs['Color'])
    mix = nodes.new('ShaderNodeMixShader')
    links.new(holdout.outputs['Color'], mix.inputs[0])
    links.new(flat.outputs[0], mix.inputs[1])
    links.new(original, mix.inputs[2])
    links.new(mix.outputs[0], terminal)
    return atlas.image


def junction_material(material, body_image, body_uv):
    tree = material.node_tree
    nodes, links = tree.nodes, tree.links
    old = nodes.get('Principled BSDF')
    assert old is not None and len(old.outputs[0].links) == 1
    outgoing = old.outputs[0].links[0].to_socket
    flat = nodes.new('ShaderNodeEmission')
    flat.label = 'Same arm pigment on the sides of the face and neck transition'
    links.new(swatch(tree, body_image, body_uv, 'Pigment sampled from CC0 upper arm'), flat.inputs['Color'])
    links.new(flat.outputs[0], outgoing)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--mask', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    sources = ROOT / args.candidate
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    mask_path = ROOT / args.mask
    meta = json.loads(mask_path.with_suffix('.json').read_text(encoding='utf-8'))
    rows = {}
    for form in ('coat_off', 'coat_on'):
        name = f'BaiQi_CC0_{form}.blend'
        bpy.ops.wm.open_mainfile(filepath=str(sources / name))
        body = bpy.data.objects['Body']
        head = bpy.data.objects['BaiQi restored authored head and face']
        body_before = mesh_fingerprint(body)
        head_before = mesh_fingerprint(head)
        body_image, uv, rgb, samples = arm_swatch(body)
        atlas = face_material(head.data.materials['BaiQi original face appearance'], body_image, uv, mask_path, meta)
        junction_material(head.data.materials['BaiQi neck junction shading'], body_image, uv)
        assert mesh_fingerprint(body) == body_before
        assert mesh_fingerprint(head) == head_before
        bpy.ops.file.pack_all()
        path = output / name
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        rows[form] = {'model_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'original_body_sha256': body_before, 'authored_head_mesh_sha256': head_before,
                      'arm_samples': samples, 'arm_reference_uv': list(uv), 'arm_reference_texel': rgb.tolist(),
                      'original_face_atlas_sha256': hashlib.sha256(atlas.packed_file.data).hexdigest(),
                      'protected_facial_art': meta['protected_source_parts']}
    (output / 'skin_tone_report.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
