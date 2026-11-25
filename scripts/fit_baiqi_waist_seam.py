"""Fit the upper skirt under the waistband while keeping the thigh clearance."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fit_baiqi_cc0_wardrobe import rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint


SKIRT = 'BaiQi pleated skirt'
WAIST = 'BaiQi fitted navy waist wrap'
ROWS, COLUMNS = 25, 120


def surface(mesh, material=None):
    return BVHTree.FromPolygons(
        [vertex.co for vertex in mesh.vertices],
        [face.vertices[:] for face in mesh.polygons if material is None or face.material_index == material],
    )


def surface_radius(tree, origin, direction):
    hit, _, _, _ = tree.ray_cast(origin + .25 * direction, -direction, .247)
    return None if hit is None else (hit - origin).dot(direction)


def tuck_upper_skirt(skirt, body, waist):
    assert len(skirt.vertices) == ROWS * COLUMNS
    heights = [skirt.vertices[row * COLUMNS].co.z for row in range(3)]
    assert heights[0] > heights[1] > heights[2]
    assert all(abs(vertex.co.z - heights[index // COLUMNS]) < 1e-6
               for index, vertex in enumerate(skirt.vertices[:3 * COLUMNS]))
    skin = next(index for index, material in enumerate(body.materials) if material.name.endswith('_SKIN'))
    skin_tree, belt_tree = surface(body, skin), surface(waist)
    changes = []
    for row, (target_clearance, strength) in enumerate(((.0036, 1.), (.0037, 1.), (.006, .35))):
        for column in range(COLUMNS):
            vertex = skirt.vertices[row * COLUMNS + column]
            origin = Vector((0., .015, vertex.co.z))
            offset = vertex.co - origin
            direction = offset.normalized()
            skin_radius = surface_radius(skin_tree, origin, direction)
            if skin_radius is None:
                continue
            belt_radius = surface_radius(belt_tree, origin, direction)
            fitted_radius = skin_radius + target_clearance
            if belt_radius is not None:
                fitted_radius = min(fitted_radius, belt_radius - .0012)
            fitted_radius = max(skin_radius + .0024, fitted_radius)
            depth = min(.011, max(0., offset.length - fitted_radius)) * strength
            # Keep the front fit where the advancing thigh crosses the hem in major attacks.
            front = math.cos(math.tau * column / COLUMNS)
            fade = min(1., max(0., (.75 - front) / .36))
            depth = depth * fade**2 * (3. - 2. * fade)
            if depth > 0.:
                vertex.co -= depth * direction
                changes.append(depth)
    assert changes
    skirt.update()
    return {'changed_vertices': len(changes), 'max_move_mm': 1000 * max(changes)}


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
    forms = {}
    for form in ('coat_on', 'coat_off'):
        base = source / f'BaiQi_CC0_{form}.blend'
        assert fingerprint(base) == manifest[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(base))
        body, head, armature, skirt, waist = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature', SKIRT, WAIST))
        assert skirt.matrix_world == body.matrix_world == waist.matrix_world
        fixed = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj != skirt}
        assert fixed[body] == manifest[form]['body_sha256']
        rig = rest_signature(armature)
        details = tuck_upper_skirt(skirt.data, body.data, waist.data)
        assert fixed == {obj: mesh_fingerprint(obj) for obj in fixed}
        assert rig == rest_signature(armature)
        target = out / base.name
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        forms[form] = {'candidate_sha256': fingerprint(target), 'cc0_body_sha256': fixed[body],
                       'original_head_sha256': fixed[head], 'skirt_waist': details}
    (out / 'skirt_waist.json').write_text(json.dumps(forms, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
