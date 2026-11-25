"""Fit the blouse neckline and its binding around the posed BaiQi neck bridge."""
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
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint
from render_baiqi_cc0_fitting import pose_arms, pose_head


PARTS = ('BaiQi fitted sleeveless blouse', 'BaiQi fitted sleeveless binding')
POSES = ('neutral', 'head_turn', 'head_turn_opposite', 'look_up', 'look_down', 'head_tilt')
NECK = 'BaiQi neck junction shading'
CLEARANCE = .0018
MAX_OFFSET = .006


def radial(point):
    return Vector((point.x - .000255, point.y + .010, 0.))


def sample_gaps(rig, head, parts, indices):
    result = {part.name: {} for part in parts}
    slot = head.data.materials.find(NECK)
    assert slot >= 0
    polygons = [face.vertices[:] for face in head.data.polygons if face.material_index == slot]
    for pose in POSES:
        pose_head(rig, pose)
        graph = bpy.context.evaluated_depsgraph_get()
        bridge = head.evaluated_get(graph)
        tree = BVHTree.FromPolygons([bridge.matrix_world @ v.co for v in bridge.data.vertices], polygons)
        for part in parts:
            evaluated = part.evaluated_get(graph)
            assert len(evaluated.data.vertices) == len(part.data.vertices), part.name
            gaps = {}
            for index in indices[part.name]:
                point = evaluated.matrix_world @ evaluated.data.vertices[index].co
                outward = radial(point).normalized()
                hit, _, _, _ = tree.ray_cast(point + .09 * outward, -outward, .17)
                if hit is not None:
                    gaps[index] = (point - hit).dot(outward)
            assert gaps, (pose, part.name)
            result[part.name][pose] = gaps
    return result


def pose_counts(samples):
    return {pose: {'tested_vertices': len(gaps), 'interior_vertices': sum(value < -.0002 for value in gaps.values()),
                   'min_gap_mm': round(1000 * min(gaps.values()), 3)} for pose, gaps in samples.items()}


def fit_neckline(rig, head, parts):
    indices = {part.name: [v.index for v in part.data.vertices if v.co.z >= 1.285 and radial(v.co).length < .086]
               for part in parts}
    modifiers = [(modifier, modifier.show_viewport) for part in parts for modifier in part.modifiers
                 if modifier.type != 'ARMATURE']
    bone_names = ('J_Bip_C_Head', 'J_Bip_C_Neck', 'J_Bip_L_UpperArm', 'J_Bip_R_UpperArm',
                  'J_Bip_L_LowerArm', 'J_Bip_R_LowerArm')
    original_pose = [(bone, bone.rotation_mode, bone.matrix_basis.copy())
                     for bone in (rig.pose.bones[name] for name in bone_names)]
    try:
        # Evaluate the weights that ship in the FBX. The outer shell thickness
        # is added at export, while the Blender clearance modifier stays local.
        for modifier, _ in modifiers:
            modifier.show_viewport = False
        pose_arms(rig, -56, 0)
        before = sample_gaps(rig, head, parts, indices)
        changes = {}
        for part in parts:
            offsets = []
            for index in indices[part.name]:
                gap = min(samples.get(index, MAX_OFFSET) for samples in before[part.name].values())
                offset = min(MAX_OFFSET, max(0., CLEARANCE - gap))
                if offset > 0.:
                    point = part.data.vertices[index].co
                    point += offset * radial(point).normalized()
                    offsets.append(offset)
            part.data.update()
            assert offsets, part.name
            changes[part.name] = {'moved_vertices': len(offsets), 'max_offset_mm': round(1000 * max(offsets), 3)}
        after = sample_gaps(rig, head, parts, indices)
        for name, values in changes.items():
            values.update(before=pose_counts(before[name]), after=pose_counts(after[name]))
            assert min(row['min_gap_mm'] for row in values['after'].values()) >= 1., name
    finally:
        for modifier, visible in modifiers:
            modifier.show_viewport = visible
        for bone, mode, basis in original_pose:
            bone.rotation_mode = mode
            bone.matrix_basis = basis
        bpy.context.view_layer.update()
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, out = ((ROOT / path).resolve() for path in (args.source, args.source_inputs, args.out))
    assert source != out and out.is_relative_to(ROOT)
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    report = {}
    for form in ('coat_on', 'coat_off'):
        path = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(path)
        assert source_hash == manifest[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        rig, head = (bpy.data.objects[name] for name in ('Armature', HEAD))
        skeleton = rest_signature(rig)
        fixed = {part: mesh_fingerprint(part) for part in bpy.context.scene.objects
                 if part.type == 'MESH' and part.name not in PARTS}
        assert fixed[bpy.data.objects['Body']] == manifest[form]['body_sha256']
        changes = fit_neckline(rig, head, [bpy.data.objects[name] for name in PARTS])
        assert all(mesh_fingerprint(part) == digest for part, digest in fixed.items())
        assert rest_signature(rig) == skeleton
        dest = out / path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(dest))
        report[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(dest),
                        'cc0_body_sha256': fixed[bpy.data.objects['Body']],
                        'original_head_sha256': fixed[head], 'parts': changes}
    (out / 'collar_clearance.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
