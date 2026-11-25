"""Close the rear crown gap using the visible fringe silhouette as a height limit."""
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
from blend_baiqi_hair_roots import CROWN
from fit_baiqi_cc0_wardrobe import rest_signature, smoothstep
from fit_baiqi_glasses_temples import surface
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint
from smooth_baiqi_fringe_side_depth import FRINGE, cutout_surface


def top_heights(tree, columns):
    heading = Vector((0., 1., 0.))
    heights = {}
    for x in columns:
        ray = Vector((x, -.32, 0.))
        for z in np.arange(1.652, 1.558, -.00025):
            ray.z = z
            if tree.ray_cast(ray, heading, .51)[0] is not None:
                heights[x] = z
                break
    return heights


def fit_crown(crown, fringe, head):
    columns = np.arange(-.129, .13, .003)
    cap = BVHTree.FromPolygons(*surface(crown))
    front = cutout_surface(fringe)
    skull = BVHTree.FromPolygons(*surface(head))
    cap_heights = top_heights(cap, columns)
    front_heights = top_heights(front, columns)
    common = [x for x in columns if x in cap_heights and x in front_heights]
    assert len(common) >= 55
    top = np.array([cap_heights[x] for x in common])
    ceiling = np.array([front_heights[x] for x in common])
    gap = np.maximum(0., ceiling - top - .0022)
    gain = np.convolve(np.pad(gap, (2, 2), mode='edge'), [.1, .2, .4, .2, .1], mode='valid')
    to_world = crown.matrix_world.copy()
    to_local = to_world.inverted()
    moves = []
    for vertex in crown.data.vertices:
        x, y, z = to_world @ vertex.co
        side = smoothstep((.107 - abs(x)) / .015) * smoothstep((abs(x) - .030) / .012)
        depth = smoothstep(1. + (z - np.interp(x, common, top)) / .040)
        rear = smoothstep((.028 - y) / .043)
        rise = .68 * side * depth * rear * np.interp(x, common, gain)
        if rise > 1e-9:
            vertex.co = to_local @ Vector((x, y + .19 * rise, z + rise))
            moves.append(float(np.hypot(rise, .19 * rise) * 1000.))
    crown.data.update()
    modified = BVHTree.FromPolygons(*surface(crown))
    head_pairs = len(cap.overlap(skull))
    assert len(modified.overlap(skull)) <= head_pairs
    assert moves and max(moves) < 30.
    roof = top_heights(modified, common)
    assert set(roof) == set(common)
    remaining = [max(0., front_heights[x] - roof[x]) for x in common]
    return {'moved_vertices': sum(distance > .001 for distance in moves), 'max_move_mm': max(moves),
            'profile_columns': len(common), 'max_fringe_above_cap_mm': (max(gap) + .0022) * 1000.,
            'remaining_fringe_above_cap_mm': max(remaining) * 1000.,
            'crown_head_pairs_before': head_pairs, 'crown_head_pairs_after': len(modified.overlap(skull)),
            'crown_fringe_pairs_before': len(cap.overlap(front)),
            'crown_fringe_pairs_after': len(modified.overlap(front))}


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
        path = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(path)
        assert source_hash == manifest[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        objects = bpy.data.objects
        rig, body, head, crown, fringe = (objects[key] for key in ('Armature', 'Body', HEAD, CROWN, FRINGE))
        protected = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects
                     if obj.type == 'MESH' and obj != crown}
        assert protected[body] == manifest[form]['body_sha256']
        skeleton = rest_signature(rig)
        result = fit_crown(crown, fringe, head)
        assert all(mesh_fingerprint(obj) == value for obj, value in protected.items())
        assert rest_signature(rig) == skeleton
        target = output / path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        records[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(target),
                         'authored_head_sha256': protected[head], 'cc0_body_sha256': protected[body], **result}
    (output / 'crown_fit.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
