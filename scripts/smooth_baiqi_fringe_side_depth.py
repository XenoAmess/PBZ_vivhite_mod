"""Fit a continuous depth profile through the rough lower side of the original fringe."""
import argparse
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from export_baiqi_game_forms import first_texture, game_uv, trim_texture_mask
from fit_baiqi_cc0_wardrobe import rest_signature
from fit_baiqi_glasses_temples import surface
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint
from soften_baiqi_side_hair import FRINGE, projected_axes, smooth


OFFSETS = np.array([-40., -30., -24., -18., -12., -6., 0., 6., 12., 18., 24.])


def cutout_surface(fringe):
    copy = fringe.copy()
    copy.data = fringe.data.copy()
    bpy.context.scene.collection.objects.link(copy)
    game_uv(copy.data)
    trim_texture_mask(copy, first_texture(copy.data.materials[0]).image)
    result = BVHTree.FromPolygons(*surface(copy))
    mesh = copy.data
    bpy.data.objects.remove(copy, do_unlink=True)
    bpy.data.meshes.remove(mesh)
    return result


def measured_profile(u, v, depth):
    row = np.rint((v + .5) / 6.).astype(int)
    sample = (u > 580.) & (u < 711.) & (v > 406.) & (v < 561.)
    centers, profiles = [], []
    for value in np.unique(row[sample]):
        indices = np.flatnonzero(sample & (row == value))
        indices = indices[np.argsort(u[indices])]
        columns, depths = u[indices], depth[indices]
        crossing = np.flatnonzero((depths[:-1] >= 0.) & (depths[1:] < 0.))
        if len(indices) < 13 or not len(crossing):
            continue
        index = crossing[0]
        start, end = depths[index:index + 2]
        center = columns[index] + (columns[index + 1] - columns[index]) * start / (start - end)
        if columns[0] + 41. <= center <= columns[-1] - 22.:
            centers.append((v[indices[0]], center))
            profiles.append(np.interp(center + OFFSETS, columns, depths))
    assert len(centers) >= 10
    locations, values = np.array(centers).T
    curve = np.polyfit(locations, values, 3)
    mean_error = np.mean(np.abs(np.polyval(curve, locations) - values))
    assert mean_error < .25
    middle = np.median(profiles, axis=0)
    depth_curve = middle.copy()
    depth_curve[1:-1] = .65 * middle[1:-1] + .175 * (middle[:-2] + middle[2:])
    return curve, depth_curve, len(centers), float(mean_error)


def smooth_fringe(fringe, head):
    mesh = fringe.data
    assert len(mesh.vertices) == 5282 and len(mesh.polygons) == 4916
    x, depth, z = np.array([vertex.co[:] for vertex in mesh.vertices]).T
    axis_x, axis_z = projected_axes(mesh, x, z)
    u = (x - axis_x[1]) / axis_x[0] * 880. - .5
    v = (1. - (z - axis_z[1]) / axis_z[0]) * 800. - .5
    curve, depth_curve, rows, error = measured_profile(u, v, depth)
    offset = u - np.polyval(curve, v)
    band = smooth((u - 603.) / 27.) * smooth((706. - u) / 19.)
    band *= smooth((v - 398.) / 30.) * smooth((578. - v) / 32.)
    band *= smooth((.059 - depth) / .025) * smooth((offset + 34.) / 13.) * smooth((22. - offset) / 10.)
    expected = np.interp(offset, OFFSETS, depth_curve)
    move = np.clip((expected - depth) * band, -.006, .006)
    changed = np.flatnonzero(np.abs(move) > 1e-7)
    head_surface = BVHTree.FromPolygons(*surface(head))
    assert not cutout_surface(fringe).overlap(head_surface)
    for index in changed:
        mesh.vertices[int(index)].co.y = depth[index] + move[index]
    mesh.update()
    assert not cutout_surface(fringe).overlap(head_surface)
    first, last = np.array([edge.vertices[:] for edge in mesh.edges]).T
    region = (band[first] > .2) & (band[last] > .2)
    before = np.abs(depth[first] - depth[last])[region] * 1000.
    after = np.abs((depth + move)[first] - (depth + move)[last])[region] * 1000.
    assert np.quantile(after, .95) < np.quantile(before, .95)
    return {'fitted_rows': rows, 'mean_profile_error_px': error, 'moved_vertices': len(changed),
            'max_move_mm': float(np.max(np.abs(move)) * 1000.), 'head_contact_pairs': 0,
            'source_edge_depth_delta_p95_mm': float(np.quantile(before, .95)),
            'fitted_edge_depth_delta_p95_mm': float(np.quantile(after, .95)),
            'source_edge_depth_delta_max_mm': float(before.max()), 'fitted_edge_depth_delta_max_mm': float(after.max())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, output = ((ROOT / path).resolve() for path in (args.source, args.source_inputs, args.out))
    assert source != output and output.is_relative_to(ROOT)
    manifest = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    for form in ('coat_on', 'coat_off'):
        name = f'BaiQi_CC0_{form}.blend'
        path = source / name
        source_hash = fingerprint(path)
        assert source_hash == manifest[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        objects = bpy.data.objects
        rig, body, head, fringe = (objects[key] for key in ('Armature', 'Body', HEAD, FRINGE))
        fixed = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj != fringe}
        assert fixed[body] == manifest[form]['body_sha256']
        skeleton = rest_signature(rig)
        result = smooth_fringe(fringe, head)
        assert all(mesh_fingerprint(obj) == value for obj, value in fixed.items())
        assert rest_signature(rig) == skeleton
        target = output / name
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        records[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(target),
                         'authored_head_sha256': fixed[head], 'cc0_body_sha256': fixed[body], **result}
    (output / 'fringe_side_depth.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
