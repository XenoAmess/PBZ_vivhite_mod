"""Blend the separate BaiQi neck bridge's corner normals into the CC0 neck."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from apply_baiqi_neck_pigment import NECK_NORMAL_MAP_MARKER
from export_baiqi_game_forms import game_uv, neck_pigment_uv
from fit_baiqi_cc0_wardrobe import rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint


BRIDGE = 'BaiQi neck junction shading'
FORMS = ('coat_on', 'coat_off')
MAP_SIZE = 512


def smooth(value):
    value = max(0., min(1., value))
    return value * value * (3. - 2. * value)


def cc0_neck_sampler(mesh):
    coordinates = [vertex.co.copy() for vertex in mesh.vertices]
    mesh.calc_loop_triangles()
    triangles = [triangle for triangle in mesh.loop_triangles
                 if mesh.materials[triangle.material_index].name.endswith('_SKIN')
                 and all(1.285 < coordinates[i].z < 1.42 for i in triangle.vertices)]
    indices = [tuple(triangle.vertices) for triangle in triangles]
    tree = BVHTree.FromPolygons(coordinates, indices, all_triangles=True)
    basis = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))

    def sample(point):
        center = Vector((.000255, -.010, point.z))
        outward = (point - center).normalized()
        hit, _, index, _ = tree.ray_cast(center + .1 * outward, -outward, .098)
        if hit is None:
            return None, None
        weights = barycentric_transform(hit, *(coordinates[i] for i in indices[index]), *basis)
        corners = [mesh.corner_normals[i].vector for i in triangles[index].loops]
        normal = sum((corner * weight for corner, weight in zip(corners, weights, strict=True)), Vector())
        return normal.normalized(), (point - hit).length

    return sample


def blend_bridge(head, body):
    mesh = head.data
    sample = cc0_neck_sampler(body.data)
    before = [item.vector.copy() for item in mesh.corner_normals]
    updated = before.copy()
    slot = mesh.materials.find(BRIDGE)
    assert slot >= 0
    bridge = {index for face in mesh.polygons if face.material_index == slot for index in face.loop_indices}
    shared = {index for face in mesh.polygons if face.material_index != slot for index in face.vertices}
    intended = set()
    for index in bridge:
        vertex = mesh.loops[index].vertex_index
        if vertex in shared:
            continue
        point = mesh.vertices[vertex].co
        if not 1.310 <= point.z < 1.378:
            continue
        target, distance = sample(point)
        if target is None or target.dot(before[index]) < .35:
            continue
        fraction = smooth((1.378 - point.z) / .018) * smooth((.012 - distance) / .006)
        if fraction > 0.:
            updated[index] = before[index].lerp(target, fraction).normalized()
            intended.add(index)

    mesh.normals_split_custom_set(updated)
    mesh.update()
    after = [item.vector for item in mesh.corner_normals]
    angles = [math.degrees(a.angle(b)) for a, b in zip(before, after, strict=True)]
    outside = max(angle for index, angle in enumerate(angles) if index not in bridge)
    assert intended and outside < .12, outside
    return {'bridge_corners_adjusted': len(intended), 'max_bridge_normal_rotation_degrees': max(angles),
            'max_outside_bridge_rotation_degrees': outside}


def raster_triangle(texture, exterior, uv, radii, normals):
    size = np.array((texture.shape[1], texture.shape[0]))
    points = uv * size - .5
    a, b, c = points
    leg1, leg2 = b - a, c - a
    determinant = leg1[0] * leg2[1] - leg1[1] * leg2[0]
    low = np.maximum(0, np.ceil(points.min(axis=0)).astype(int))
    high = np.minimum(size - 1, np.floor(points.max(axis=0)).astype(int))
    if abs(determinant) < 1e-6 or np.any(high < low):
        return
    rows, columns = np.mgrid[low[1]:high[1] + 1, low[0]:high[0] + 1]
    x, y = columns - a[0], rows - a[1]
    v = (x * leg2[1] - y * leg2[0]) / determinant
    w = (leg1[0] * y - leg1[1] * x) / determinant
    weights = np.stack((1. - v - w, v, w), axis=-1)
    rank = weights @ radii
    covered = (weights.min(axis=-1) >= -1e-7) & (rank > exterior[rows, columns])
    values = weights[covered] @ normals
    lengths = np.linalg.norm(values, axis=-1, keepdims=True)
    valid = lengths[:, 0] > .4
    y, x = rows[covered][valid], columns[covered][valid]
    texture[y, x] = values[valid] / lengths[valid]
    exterior[y, x] = rank[covered][valid]


def bake_bridge_normals(source, target):
    game_uv(source)
    neck_pigment_uv(source)
    source.calc_loop_triangles()
    source.calc_tangents(uvmap=source.uv_layers.active.name)
    uvs = np.array([point.vector for point in source.uv_layers.active.uv])
    normal = np.array([corner.vector for corner in source.corner_normals])
    desired = np.array([corner.vector for corner in target.corner_normals])
    tangent = np.array([loop.tangent for loop in source.loops])
    bitangent = np.cross(normal, tangent) * np.array([loop.bitangent_sign for loop in source.loops])[:, None]
    vectors = np.column_stack((np.sum(desired * tangent, axis=1),
                               -np.sum(desired * bitangent, axis=1), np.sum(desired * normal, axis=1)))
    vectors[np.linalg.norm(desired - normal, axis=1) < .0003] = (0, 0, 1)
    radius = np.array([math.hypot(v.co.x - .000255, v.co.y + .010) for v in source.vertices])
    slot = source.materials.find(BRIDGE)
    texture = np.zeros((MAP_SIZE, MAP_SIZE, 3), dtype=np.float32)
    texture[..., 2] = 1.
    exterior = np.full(texture.shape[:2], -1., dtype=np.float32)
    for triangle in source.loop_triangles:
        if triangle.material_index != slot:
            continue
        loops = list(triangle.loops)
        for shift in (-1, 0):
            raster_triangle(texture, exterior, uvs[loops] + (shift, 0.),
                            radius[list(triangle.vertices)], vectors[loops])

    covered = exterior >= 0
    assert covered.all(), 'Neck UV has uncovered normal samples'
    # The UV v coordinate clamps at the top. Return smoothly to a flat normal there.
    v = (np.arange(MAP_SIZE) + .5) / MAP_SIZE
    texture[..., :2] *= np.clip((1. - v) / .045, 0., 1.)[:, None, None]
    texture[..., 2] = np.sqrt(np.maximum(0., 1. - np.square(texture[..., :2]).sum(axis=2)))
    return np.rint((texture * .5 + .5) * 255).astype(np.uint8)


def save_bridge_map(path, rgb):
    image = bpy.data.images.new(path.stem, rgb.shape[1], rgb.shape[0], alpha=False)
    image.colorspace_settings.name = 'Non-Color'
    rgba = np.ones((*rgb.shape[:2], 4), dtype=np.float32)
    rgba[..., :3] = rgb / 255.
    image.pixels.foreach_set(rgba.ravel())
    image.filepath_raw = str(path)
    image.file_format = 'PNG'
    image.save()
    bpy.data.images.remove(image)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, output = ((ROOT / path).resolve() for path in (args.source, args.source_inputs, args.out))
    assert source != output and output.is_relative_to(ROOT)
    output.mkdir(parents=True, exist_ok=True)
    expected = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    records = {}
    first_map = None
    for form in FORMS:
        filename = f'BaiQi_CC0_{form}.blend'
        path = source / filename
        source_hash = fingerprint(path)
        assert source_hash == expected[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        body, head, rig = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature'))
        geometry = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH'}
        body_normals = [tuple(normal.vector) for normal in body.data.corner_normals]
        skeleton = rest_signature(rig)
        assert geometry[body] == expected[form]['body_sha256']
        assert not head.data.has_custom_normals, 'Expected the baseline automatic head normals'
        original = head.data.copy()
        fit = blend_bridge(head, body)
        baked = bake_bridge_normals(original, head.data)
        bpy.data.meshes.remove(original)
        if first_map is None:
            first_map = baked
        else:
            assert np.array_equal(first_map, baked), 'Neck normal bake differs between forms'
        head.data[NECK_NORMAL_MAP_MARKER] = True
        assert all(mesh_fingerprint(obj) == digest for obj, digest in geometry.items())
        assert body_normals == [tuple(normal.vector) for normal in body.data.corner_normals]
        assert skeleton == rest_signature(rig)
        destination = output / filename
        bpy.ops.wm.save_as_mainfile(filepath=str(destination))
        records[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(destination),
                         'cc0_body_sha256': geometry[body], 'authored_head_sha256': geometry[head], **fit}
    normal_path = output / 'T_BaiQiNative_NeckBridge.png'
    save_bridge_map(normal_path, first_map)
    records['native_normal_sha256'] = fingerprint(normal_path)
    (output / 'neck_normals.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
    print(records, flush=True)


if __name__ == '__main__':
    main()
