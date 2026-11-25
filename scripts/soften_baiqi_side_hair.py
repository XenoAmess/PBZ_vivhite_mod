"""Fair the depth of the front bob's lower side outline against its original alpha."""
import argparse
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from export_baiqi_game_forms import first_texture, game_uv
from fit_baiqi_cc0_wardrobe import rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint


FRINGE = 'BaiQi bob front'
MASK_EDGE = .25  # The exported hair cutout uses the same alpha threshold.
SIDE_BAND = .013
MAX_SHIFT = .009


def smooth(weight):
    weight = np.clip(weight, 0., 1.)
    return weight * weight * (3. - 2. * weight)


def projected_axes(mesh, x, z):
    projected = mesh.copy()
    game_uv(projected)
    links = np.array([loop.vertex_index for loop in projected.loops])
    uv = np.array([pair.vector[:] for pair in projected.uv_layers.active.uv])
    bpy.data.meshes.remove(projected)
    lower = z[links] < 1.432
    axes = []
    for uv_axis, world_axis in [(uv[lower, 0], x[links][lower]), (uv[lower, 1], z[links][lower])]:
        mapping = np.polyfit(uv_axis, world_axis, 1)
        assert np.max(np.abs(np.polyval(mapping, uv_axis) - world_axis)) < 1e-5
        axes.append(mapping)
    return axes


def outline_samples(alpha, sign, to_x, to_z, surface):
    width, height = alpha.shape[1], alpha.shape[0]
    samples = []
    for row in range(548, 618):
        scan = alpha[row]
        opaque = np.flatnonzero(scan > MASK_EDGE)
        assert len(opaque) > 0
        inside = int(opaque[-1] if sign < 0 else opaque[0])
        outside = inside - sign
        fraction = (scan[inside] - MASK_EDGE) / (scan[inside] - scan[outside])
        column = inside + (outside - inside) * fraction
        x = np.polyval(to_x, (column + .5) / width)
        z = np.polyval(to_z, 1. - (row + .5) / height)
        hit, _, _, _ = surface.ray_cast(Vector((x, -.35, z)), Vector((0., 1., 0.)), .60)
        if hit is not None:
            samples.append((row, x, hit.y))
    assert len(samples) > 40
    return np.array(samples).T


def fair_outline(fringe):
    mesh = fringe.data
    assert len(mesh.vertices) == 5282 and len(mesh.polygons) == 4916
    image = first_texture(mesh.materials[0]).image
    width, height = image.size
    assert (width, height) == (880, 800)
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    alpha = pixels.reshape(height, width, 4)[::-1, :, 3]
    coordinates = np.array([vertex.co[:] for vertex in mesh.vertices])
    x, y, z = coordinates.T
    to_x, to_z = projected_axes(mesh, x, z)
    mesh.calc_loop_triangles()
    surface = BVHTree.FromPolygons([Vector(point) for point in coordinates],
                                   [triangle.vertices[:] for triangle in mesh.loop_triangles], all_triangles=True)
    rows = (1. - (z - to_z[1]) / to_z[0]) * height - .5
    below_ear = smooth((rows - 546.) / 12.) * smooth((620. - rows) / 10.)
    movement = np.zeros_like(y)
    for side in (-1, 1):
        sample_rows, edge_x, edge_y = outline_samples(alpha, side, to_x, to_z, surface)
        sweep = np.polynomial.Polynomial.fit(sample_rows, edge_y, 3)
        distance = (x - np.interp(rows, sample_rows, edge_x)) * side
        # Replace the steep projected turn near the original line without moving its image coordinates.
        target = sweep(rows) - .8 * distance
        blend = smooth((SIDE_BAND - np.abs(distance)) / (SIDE_BAND * .67)) * below_ear * (x * side > .072)
        movement += np.clip(target - y, -MAX_SHIFT, MAX_SHIFT) * blend
    affected = np.flatnonzero(np.abs(movement) > 1e-9)
    assert 0 < len(affected) < 200 and np.abs(movement).max() <= MAX_SHIFT + 1e-10
    for index in affected:
        mesh.vertices[int(index)].co.y = y[index] + movement[index]
    mesh.update()
    return {'moved_vertices': len(affected), 'max_depth_move_mm': float(np.abs(movement).max() * 1000.)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, out = ((ROOT / path).resolve() for path in (args.source, args.source_inputs, args.out))
    assert source != out and out.is_relative_to(ROOT)
    manifest = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    for form in ('coat_on', 'coat_off'):
        path = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(path)
        assert source_hash == manifest[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        objects = bpy.data.objects
        head, body, rig, fringe = (objects[name] for name in (HEAD, 'Body', 'Armature', FRINGE))
        frozen = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj != fringe}
        assert frozen[body] == manifest[form]['body_sha256']
        skeleton = rest_signature(rig)
        details = fair_outline(fringe)
        assert frozen == {obj: mesh_fingerprint(obj) for obj in frozen}
        assert skeleton == rest_signature(rig)
        target = out / path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        results[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(target),
                         'cc0_body_sha256': frozen[body], 'original_head_sha256': frozen[head], 'fringe': details}
    (out / 'side_fringe.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
