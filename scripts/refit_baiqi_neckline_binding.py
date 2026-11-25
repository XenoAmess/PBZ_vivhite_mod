"""Refit the existing white binding to the blouse lip while retaining its neck edge."""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fit_baiqi_cc0_wardrobe import rest_signature
from fit_baiqi_collar_clearance import PARTS, NECK, radial
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint
from tailor_baiqi_open_edges import boundary_loops


PROFILE = ((0., .00026, 0.), (.18, .00064, .38), (.50, .00080, .83),
           (.84, .00056, .93), (1., .00023, .75))
WIDTH = .0042


def vertex_weights(vertex):
    return {group.group: group.weight for group in vertex.groups}


def refit(blouse, binding, head):
    cloth = blouse.data
    trim = binding.data
    rings, centres = boundary_loops(cloth)
    openings = [ring for ring in rings if min(cloth.vertices[i].co.z for i in ring) > 1.18]
    neck = max(openings, key=lambda ring: sum(cloth.vertices[i].co.z for i in ring) / len(ring))
    assert len(openings) == 3 and len(trim.vertices) == len(PROFILE) * sum(map(len, openings))
    start = len(PROFILE) * sum(map(len, openings[:openings.index(neck)]))
    coords = [point.co.copy() for point in cloth.vertices]
    upper_blouse = BVHTree.FromPolygons(coords, [face.vertices[:] for face in cloth.polygons
                                                if max(coords[i].z for i in face.vertices) > 1.265])
    bridge = head.data
    slot = bridge.materials.find(NECK)
    assert slot >= 0
    neck_surface = BVHTree.FromPolygons([point.co for point in bridge.vertices],
                                       [face.vertices[:] for face in bridge.polygons if face.material_index == slot])
    distances = []
    for row, index in enumerate(neck):
        anchor = cloth.vertices[index]
        previous, following = neck[row - 1], neck[(row + 1) % len(neck)]
        normal = anchor.normal.normalized()
        across = normal.cross(coords[following] - coords[previous]).normalized()
        if across.dot((centres[index] + centres[previous]) * .5 - anchor.co) < 0.:
            across.negate()
        for column, (position, raise_by, fraction) in enumerate(PROFILE):
            vertex = trim.vertices[start + len(PROFILE) * row + column]
            assert vertex_weights(vertex) == vertex_weights(anchor)
            if fraction == 0.:
                continue
            frame = anchor.co + across * (position * WIDTH)
            hit, _, _, _ = upper_blouse.ray_cast(frame + .014 * normal, -normal, .026)
            if hit is not None:
                step = hit - frame
                frame += step if step.length <= .0013 else step.normalized() * .0013
            fitted = frame + (raise_by + .00055) * normal
            outward = radial(fitted).normalized()
            skin, _, _, _ = neck_surface.ray_cast(fitted + .09 * outward, -outward, .17)
            if skin is not None:
                clearance = (fitted - skin).dot(outward)
                fitted += max(0., .0015 - clearance) * outward
            destination = vertex.co.lerp(fitted, fraction)
            distances.append((destination - vertex.co).length)
            vertex.co = destination
    trim.update()
    assert distances and max(distances) <= .003
    return {'neck_rows': len(neck), 'moved_vertices': sum(value > 1e-7 for value in distances),
            'max_delta_mm': 1000 * max(distances), 'neck_edge_vertices_unchanged': len(neck)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, out = ((ROOT / path).resolve() for path in (args.source, args.source_inputs, args.out))
    assert source != out and out.is_relative_to(ROOT)
    expected = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    for form in ('coat_on', 'coat_off'):
        filename = f'BaiQi_CC0_{form}.blend'
        path = source / filename
        source_hash = fingerprint(path)
        assert source_hash == expected[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        body, head, rig, blouse, binding = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature', *PARTS))
        fixed = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj != binding}
        skeleton = rest_signature(rig)
        assert fixed[body] == expected[form]['body_sha256']
        changes = refit(blouse, binding, head)
        assert all(mesh_fingerprint(obj) == value for obj, value in fixed.items())
        assert skeleton == rest_signature(rig)
        result = out / filename
        bpy.ops.wm.save_as_mainfile(filepath=str(result))
        report[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(result),
                        'cc0_body_sha256': fixed[body], 'authored_head_sha256': fixed[head], **changes}
    (out / 'neckline_binding.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(report, flush=True)


if __name__ == '__main__':
    main()
