"""Ease the sleeveless blouse armholes around the unchanged CC0 arm motion."""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fit_baiqi_cc0_wardrobe import rest_signature
from fit_baiqi_collar_clearance import PARTS
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint
from render_baiqi_cc0_fitting import pose_arms
from tailor_baiqi_open_edges import boundary_loops


POSES = ((-56, 0), (0, 0), (-7, 0), (30, 0), (-16, 58), (-39, 70), (34, 35), (-8, 30))
MAX_LIFT = .002
BINDING_ROWS = 5


def armhole_rings(blouse, binding):
    mesh = blouse.data
    openings, _ = boundary_loops(mesh)
    rings = [ring for ring in openings if min(mesh.vertices[i].co.z for i in ring) > 1.18]
    assert len(rings) == 3 and len(binding.data.vertices) == BINDING_ROWS * sum(map(len, rings))
    sleeves = [(ring, BINDING_ROWS * sum(map(len, rings[:index]))) for index, ring in enumerate(rings)
               if abs(sum(mesh.vertices[i].co.x for i in ring) / len(ring)) > .07]
    assert len(sleeves) == 2
    return rings, sleeves


def measure_contacts(blouse, binding, body, rig, anchors):
    bones = [rig.pose.bones[f'J_Bip_{side}_{part}Arm'] for side in ('L', 'R') for part in ('Upper', 'Lower')]
    rest = [(bone, bone.rotation_mode, bone.matrix_basis.copy()) for bone in bones]
    depth = dict.fromkeys(anchors, 0.)
    hits = 0
    try:
        for elevation, advance in POSES:
            pose_arms(rig, elevation, advance)
            graph = bpy.context.evaluated_depsgraph_get()
            cloth, trim, skin = (obj.evaluated_get(graph) for obj in (blouse, binding, body))
            # The final Solidify modifier keeps the first shell in source vertex order.
            assert blouse.modifiers[-1].type == 'SOLIDIFY'
            assert len(cloth.data.vertices) == 2 * len(blouse.data.vertices)
            assert len(trim.data.vertices) == len(binding.data.vertices)
            slots = {i for i, material in enumerate(skin.data.materials)
                     if material.name.startswith('Original CC0 skin')}
            vertices = [skin.matrix_world @ point.co for point in skin.data.vertices]
            faces = [face.vertices[:] for face in skin.data.polygons if face.material_index in slots
                     and min(vertices[i].z for i in face.vertices) > 1.08]
            assert faces
            skin_surface = BVHTree.FromPolygons(vertices, faces)
            for index, edge_start in anchors.items():
                vertex = cloth.data.vertices[index]
                outward = (cloth.matrix_world.to_3x3() @ vertex.normal).normalized()
                points = [cloth.matrix_world @ vertex.co]
                points.extend(trim.matrix_world @ trim.data.vertices[i].co
                              for i in range(edge_start, edge_start + BINDING_ROWS))
                for point in points:
                    contact, normal, _, _ = skin_surface.ray_cast(point + .045 * outward, -outward, .068)
                    if contact is None or normal.dot(outward) < .26:
                        continue
                    gap = (point - contact).dot(outward)
                    # Ignore crossings of the opposite arm or the far side of the ribs.
                    if -.0072 < gap < -.0002:
                        depth[index] = max(depth[index], .00040 - gap)
                        hits += 1
    finally:
        for bone, mode, basis in rest:
            bone.rotation_mode = mode
            bone.matrix_basis = basis
        bpy.context.view_layer.update()
    return depth, hits


def match_openings(blouse, binding, body, rig):
    mesh = blouse.data
    rings, sleeves = armhole_rings(blouse, binding)
    anchors = {index: start + row * BINDING_ROWS for ring, start in sleeves for row, index in enumerate(ring)}
    required, before = measure_contacts(blouse, binding, body, rig, anchors)
    rim = {}
    for ring, _ in sleeves:
        for row, i in enumerate(ring):
            smooth = .25 * required[ring[row - 1]] + .5 * required[i] + .25 * required[ring[(row + 1) % len(ring)]]
            rim[i] = mesh.vertices[i].normal.normalized() * min(MAX_LIFT, max(.84 * required[i], smooth))
    protected = set().union(*map(set, rings))
    adjoining = {}
    for edge in mesh.edges:
        a, b = edge.vertices
        for anchor, neighbor in ((a, b), (b, a)):
            if anchor in rim and neighbor not in protected:
                offset = .42 * rim[anchor]
                if offset.length > adjoining.get(neighbor, Vector()).length:
                    adjoining[neighbor] = offset
    offsets = {**adjoining, **rim}
    for i, offset in offsets.items():
        mesh.vertices[i].co += offset
    for index, start in anchors.items():
        for row in range(BINDING_ROWS):
            binding.data.vertices[start + row].co += rim[index]
    mesh.update()
    binding.data.update()
    _, after = measure_contacts(blouse, binding, body, rig, anchors)
    return {'cloth_vertices': sum(v.length > 1e-7 for v in offsets.values()),
            'binding_vertices': BINDING_ROWS * sum(v.length > 1e-7 for v in rim.values()),
            'max_move_mm': 1000 * max(v.length for v in rim.values()), 'near_skin_samples': [before, after]}


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
        path = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(path)
        assert source_hash == expected[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        body, head, rig, blouse, binding = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature', *PARTS))
        fixed = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects
                 if obj.type == 'MESH' and obj not in {blouse, binding}}
        skeleton = rest_signature(rig)
        assert fixed[body] == expected[form]['body_sha256']
        result = match_openings(blouse, binding, body, rig)
        assert all(mesh_fingerprint(obj) == digest for obj, digest in fixed.items())
        assert rest_signature(rig) == skeleton
        target = out / path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        report[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(target),
                        'cc0_body_sha256': fixed[body], 'authored_head_sha256': fixed[head], **result}
    (out / 'armhole_clearance.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(report, flush=True)


if __name__ == '__main__':
    main()
