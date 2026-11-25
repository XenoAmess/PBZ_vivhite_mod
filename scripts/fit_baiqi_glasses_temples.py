"""Seat the existing glasses temples against the actual cutout frame."""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from export_baiqi_game_forms import first_texture, game_uv, trim_texture_mask
from finish_baiqi_surfaces import EXPORT_THICKNESS, FRAMES
from fit_baiqi_cc0_wardrobe import rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint


TEMPLE_PREFIX = 'BaiQi glasses temple '
RING_LENGTH = 8
DISPLACEMENT = (0., .19, .78, 1.)


def surface(obj):
    return [obj.matrix_world @ vertex.co for vertex in obj.data.vertices], [face.vertices[:] for face in obj.data.polygons]


def cutout_rim(frame):
    duplicate = frame.copy()
    duplicate.data = frame.data.copy()
    bpy.context.scene.collection.objects.link(duplicate)
    for modifier in list(duplicate.modifiers):
        if modifier.name != EXPORT_THICKNESS:
            duplicate.modifiers.remove(modifier)
    game_uv(duplicate.data)
    trim_texture_mask(duplicate, first_texture(duplicate.data.materials[0]).image)
    bpy.context.view_layer.objects.active = duplicate
    assert bpy.ops.object.modifier_apply(modifier=EXPORT_THICKNESS) == {'FINISHED'}
    points, polygons = surface(duplicate)
    data = duplicate.data
    bpy.data.objects.remove(duplicate, do_unlink=True)
    bpy.data.meshes.remove(data)
    return points, polygons


def fit_temple(temple, rim_points, rim_faces, head_surface):
    mesh = temple.data
    origin = [temple.matrix_world @ vertex.co for vertex in mesh.vertices]
    assert len(origin) == RING_LENGTH * len(DISPLACEMENT)
    ordered = sorted(range(len(origin)), key=lambda i: origin[i].y)
    rings = [ordered[i:i + RING_LENGTH] for i in range(0, len(ordered), RING_LENGTH)]
    front = sum((origin[i] for i in rings[-1]), Vector()) / RING_LENGTH
    side = 1 if front.x > 0. else -1
    outer_faces = [face for face in rim_faces if all(side * rim_points[i].x > .063 for i in face)]
    frame_surface = BVHTree.FromPolygons(rim_points, outer_faces)
    contact, _, _, distance = frame_surface.find_nearest(front)
    assert .004 < distance < .030, (temple.name, distance)
    shift = contact - front
    local_shift = temple.matrix_world.inverted().to_3x3() @ shift
    for ring, strength in zip(rings, DISPLACEMENT, strict=True):
        for index in ring:
            mesh.vertices[index].co += strength * local_shift
    mesh.update()
    vertices, faces = surface(temple)
    fitted = sum((vertices[i] for i in rings[-1]), Vector()) / RING_LENGTH
    error = (fitted - contact).length
    stem_surface = BVHTree.FromPolygons(vertices, faces)
    head_pairs = len(stem_surface.overlap(head_surface))
    frame_pairs = len(stem_surface.overlap(frame_surface))
    assert error < 1e-5 and head_pairs == 0 and frame_pairs > 0, (temple.name, error, head_pairs, frame_pairs)
    return {'initial_gap_mm': 1000 * distance, 'final_center_gap_mm': 1000 * error,
            'moved_vertices': RING_LENGTH * (len(DISPLACEMENT) - 1), 'rim_contact_pairs': frame_pairs,
            'head_contact_pairs': head_pairs, 'contact': list(contact)}


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
    records = {}
    for form in ('coat_on', 'coat_off'):
        filename = f'BaiQi_CC0_{form}.blend'
        path = source / filename
        source_hash = fingerprint(path)
        assert source_hash == expected[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        body, head, rig, frame = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature', FRAMES))
        temples = {obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.name.startswith(TEMPLE_PREFIX)}
        assert len(temples) == 2
        fixed = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj not in temples}
        skeleton = rest_signature(rig)
        assert fixed[body] == expected[form]['body_sha256']
        rim_points, rim_faces = cutout_rim(frame)
        head_surface = BVHTree.FromPolygons(*surface(head))
        result = {obj.name: fit_temple(obj, rim_points, rim_faces, head_surface)
                  for obj in sorted(temples, key=lambda obj: obj.name)}
        assert all(mesh_fingerprint(obj) == value for obj, value in fixed.items())
        assert rest_signature(rig) == skeleton
        target = out / filename
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        records[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(target),
                         'cc0_body_sha256': fixed[body], 'authored_head_sha256': fixed[head], 'temples': result}
    (out / 'glasses_temples.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
    print(records, flush=True)


if __name__ == '__main__':
    main()
