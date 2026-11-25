"""Unfold the crossed rear coat faces and fit the existing hem binding."""
import argparse
import json
from pathlib import Path
import shutil
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fit_baiqi_cc0_wardrobe import rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint
from tailor_baiqi_open_edges import make_binding


COAT = 'BaiQi open coat body'
BINDING = 'BaiQi open coat binding'
CENTRE = .3
REAR_COLUMNS = ((91, 372, 3.6), (94, 370, 3.7), (96, 369, 3.9), (98, 364, 3.6),
                (99, 365, 2.4), (103, 363, 4.5), (105, 366, 6.4), (104, 367, 8.))


def triangle_area(points):
    x, z = points[:, (0, 2)].T
    return float(x @ (np.roll(z, -1) - np.roll(z, 1)))


def unfold_columns(points, triangles, indices):
    # Align the small irregular crest at the hem before unrolling the horizontal fold.
    for ids, height in [((99, 100, 103, 105, 363, 365, 366), 878.98), ((98, 364), 880.07)]:
        points[list(ids), 2] += .85 * (height - points[list(ids), 2])
    columns = {vertex: column for column, vertex in enumerate(indices)}
    moves = np.zeros(len(columns))
    for left, right, offset in REAR_COLUMNS:
        for vertex, sign in ((left, -1), (right, 1)):
            moves[columns[vertex]] = CENTRE + sign * offset - points[vertex, 0]

    constraints = []
    for triangle in triangles:
        row = np.zeros_like(moves)
        z = points[triangle, 2]
        derivatives = np.roll(z, -1) - np.roll(z, 1)
        for vertex, coefficient in zip(triangle, derivatives, strict=True):
            if vertex in columns:
                row[columns[vertex]] = coefficient
        length_sq = row @ row
        if length_sq > 1e-12:
            area = triangle_area(points[triangle])
            minimum = max(min(area, 16.), 1. if z.max() < 885. else 8.)
            constraints.append((row, minimum - area, length_sq))

    # With heights fixed, the projected area is linear in horizontal displacement.
    for _ in range(4000):
        for row, bound, length_sq in constraints:
            error = bound - row @ moves
            if error > 0.:
                moves += (error / length_sq) * row
    assert all(row @ moves >= bound - .05 for row, bound, _ in constraints)
    points[indices, 0] += moves
    assert all(triangle_area(points[t]) > .5 for t in triangles)


def fair_rear_depth(points, original, triangles):
    tree = BVHTree.FromPolygons([Vector(point * .001) for point in original], triangles.tolist(), all_triangles=True)

    def sample(x, z):
        hit, _, _, _ = tree.ray_cast(Vector((.001 * x, -.5, .001 * z)), Vector((0., 1., 0.)), .45)
        return None if hit is None else 1000. * hit.y

    anchors = np.array([-53., -40., -31., 31., 40., 53.])
    for index, (x, y, z) in enumerate(points):
        if not (abs(x - CENTRE) < 55. and y < -69. and 873. < z < 981.):
            continue
        rows = [[sample(anchor, max(884., z + offset)) for anchor in anchors]
                for offset in (-4., -2., 0., 2., 4.)]
        rows = [row for row in rows if all(value is not None for value in row)]
        if not rows:
            continue
        profile = np.polynomial.polynomial.polyfit(anchors, np.mean(rows, axis=0), 2)
        target = np.polynomial.polynomial.polyval(x, profile)
        radial = np.clip((55. - abs(x - CENTRE)) / 43., 0., 1.)
        vertical = np.clip((981. - z) / 21., 0., 1.)
        blend = radial**2 * (3. - 2. * radial) * vertical**2 * (3. - 2. * vertical)
        points[index, 1] += np.clip(target - y, -8., 5.) * blend


def straighten_rear(coat):
    mesh = coat.data
    assert len(mesh.vertices) == 1376 and len(mesh.polygons) == 2392
    mesh.calc_loop_triangles()
    triangles = np.array([triangle.vertices[:] for triangle in mesh.loop_triangles])
    original = np.array([tuple(vertex.co) for vertex in mesh.vertices]) * 1000.
    points = original.copy()
    indices = [v.index for v in mesh.vertices
               if abs(v.co.x - .0003) < .017 and v.co.y < -.075 and .873 < v.co.z < .964 and v.index != 90]
    selection = set(indices)
    connected = np.array([t for t in triangles if selection.intersection(t)])
    inverted = sum(triangle_area(points[triangle]) < 0. for triangle in connected)
    assert inverted > 0
    unfold_columns(points, connected, indices)
    fair_rear_depth(points, original, triangles)
    movement = np.linalg.norm(points - original, axis=1)
    changed = np.flatnonzero(movement > 0.)
    assert 0 < len(changed) <= 50 and movement.max() < 21.
    for index in changed:
        mesh.vertices[int(index)].co = points[index] * .001
    mesh.update()
    return {'moved_vertices': len(changed), 'max_move_mm': float(movement.max()),
            'rear_triangles_with_inverted_projection_before': inverted,
            'rear_triangles_with_inverted_projection_after': 0}


def refit_binding(coat, binding):
    name = 'BaiQi rear hem binding transfer'
    make_binding(coat, name, binding.data.materials[0], lambda ring: len(ring) > 70, .0046)
    transfer = bpy.data.objects[name]
    mesh = transfer.data
    assert [face.vertices[:] for face in mesh.polygons] == [face.vertices[:] for face in binding.data.polygons]
    updates = [(old, new.co.copy(), (old.co - new.co).length)
               for old, new in zip(binding.data.vertices, mesh.vertices, strict=True)
               if (old.co - new.co).length > 1e-6]
    assert updates and len(updates) < 100 and max(delta for _, _, delta in updates) < .022
    for vertex, coordinates, _ in updates:
        assert abs(vertex.co.x) < .06 and vertex.co.y < -.08 and .86 < vertex.co.z < .90
        vertex.co = coordinates
    binding.data.update()
    bpy.data.objects.remove(transfer, do_unlink=True)
    bpy.data.meshes.remove(mesh)
    return {'moved_vertices': len(updates), 'max_move_mm': 1000 * max(delta for _, _, delta in updates)}


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
    visible = source / 'BaiQi_CC0_coat_on.blend'
    hidden = source / 'BaiQi_CC0_coat_off.blend'
    assert fingerprint(visible) == manifest['coat_on']['source_sha256']
    assert fingerprint(hidden) == manifest['coat_off']['source_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(visible))
    objects = bpy.data.objects
    fixed = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects
             if obj.type == 'MESH' and obj.name not in (COAT, BINDING)}
    assert fixed[objects['Body']] == manifest['coat_on']['body_sha256']
    skeleton = rest_signature(objects['Armature'])
    details = straighten_rear(objects[COAT])
    binding = refit_binding(objects[COAT], objects[BINDING])
    assert fixed == {obj: mesh_fingerprint(obj) for obj in fixed}
    assert skeleton == rest_signature(objects['Armature'])
    result = out / visible.name
    bpy.ops.wm.save_as_mainfile(filepath=str(result))
    shutil.copyfile(hidden, out / hidden.name)
    report = {'coat_on_sha256': fingerprint(result), 'coat_off_sha256': fingerprint(out / hidden.name),
              'cc0_body_sha256': fixed[objects['Body']], 'original_head_sha256': fixed[objects[HEAD]],
              'coat': details, 'binding': binding}
    (out / 'coat_rear_hem.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
