"""Export an editor-only proof of a native driver and intact CC0 deform branch."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Quaternion


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tools/blender_libs'),
                str(ROOT / 'vendor/UEFormat/plugins/blender')]

from baiqi_cc0_motion import Cc0Motion, SOUL_TO_CC0
from fit_baiqi_cc0_wardrobe import rest_signature
from io_scene_ueformat.importer.import_context import UEFormatImport
from io_scene_ueformat.options import UEModelOptions
from lock_baiqi_cc0_body import mesh_fingerprint


NECK_CARRIER = 'BaiQi_NeckFromHead'


def add_branch(native, cc0, calibrated=None):
    names = {bone.name: 'BaiQi_' + bone.name for bone in cc0.data.bones}
    basis = Matrix.Rotation(math.pi, 4, 'Z')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = native
    native.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    edit = native.data.edit_bones
    for bone in cc0.data.bones:
        new = edit.new(names[bone.name])
        new.parent = edit[names[bone.parent.name]] if bone.parent else edit['root']
        new.use_connect = False
        absolute = basis @ (calibrated[bone.name] if calibrated else bone.matrix_local)
        absolute.translation *= 100
        new.matrix = absolute
        new.length = bone.length * 100
    carrier = edit.new(NECK_CARRIER)
    carrier.parent = edit['root']
    carrier.head = (0, 0, 0)
    carrier.tail = (0, 0, 1)
    bpy.ops.object.mode_set(mode='OBJECT')
    return names


def bind_fixture(body, native, names):
    fixture = body.copy()
    fixture.data = body.data.copy()
    fixture.name = 'BaiQi_CC0_bridge_probe_mesh'
    bpy.context.scene.collection.objects.link(fixture)
    fixture.hide_select = False
    fixture.modifiers.clear()
    fixture.parent = native
    fixture.matrix_world = Matrix.Identity(4)
    fixture.data.transform(Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Scale(100., 4), shape_keys=True)
    for group in fixture.vertex_groups:
        group.name = names[group.name]
    modifier = fixture.modifiers.new('CC0 weights on separate deform branch', 'ARMATURE')
    modifier.object = native
    return fixture


def export_fixture(path):
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, add_leaf_bones=False, bake_anim=False,
                             use_mesh_modifiers=False, mesh_smooth_type='FACE', object_types={'ARMATURE', 'MESH'},
                             armature_nodetype='NULL', use_armature_deform_only=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = ROOT / args.out
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / args.candidate))
    cc0 = bpy.data.objects['Armature']
    body = bpy.data.objects['Body']
    original = mesh_fingerprint(body)
    assert original == body['baiqi_cc0_geometry_sha256']
    cc0.name = 'Original CC0 rig'
    existing = set(bpy.data.objects)
    UEFormatImport(UEModelOptions(scale_factor=1., reorient_bones=False, import_sockets=False,
                                  import_morph_targets=False)).import_file(ROOT / 'repro/game_reference/Hun_Body_Simple.uemodel')
    imported = list(set(bpy.data.objects) - existing)
    native = next(obj for obj in imported if obj.type == 'ARMATURE')
    for obj in imported:
        if obj.type == 'MESH':
            bpy.data.objects.remove(obj, do_unlink=True)
    native.name = 'Armature'
    rest = rest_signature(native)
    assert len(rest) == 264
    mapping = Cc0Motion(native, cc0)
    branches = add_branch(native, cc0)
    new_rest = rest_signature(native)
    for name, (parent, matrix) in rest.items():
        new_parent, new_matrix = new_rest[name]
        assert parent == new_parent and name in native.data.bones
        assert max(abs(a - b) for first, second in zip(matrix, new_matrix) for a, b in zip(first, second)) < .00015, name
    fixture = bind_fixture(body, native, branches)
    bpy.ops.object.select_all(action='DESELECT')
    native.select_set(True)
    fixture.select_set(True)
    bpy.context.view_layer.objects.active = native
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = .01
    path = output / 'BaiQi_native_bridge_probe.fbx'
    export_fixture(path)
    assert mesh_fingerprint(body) == original
    calibrations = []
    for target, donor in mapping.links.items():
        if target == 'Root':
            continue
        # Stored in Blender's native geometry basis. Engine readback supplies
        # an explicit axis conversion before applying these rotation offsets.
        target_at_source_rest = SOUL_TO_CC0.inverted() @ mapping.world_alignment[target]
        relative = mapping.source_rest[donor].inverted() @ target_at_source_rest
        calibrations.append({'source': donor, 'target': branches[target], 'offset_wxyz_blender': list(relative)})
    calibration = output / 'BaiQi_native_bridge_calibration.fbx'
    mapping.apply()
    bpy.context.view_layer.update()
    basis = Matrix.Rotation(math.pi, 4, 'Z')
    bpy.ops.object.mode_set(mode='EDIT')
    edit = native.data.edit_bones
    for bone in cc0.pose.bones:
        matrix = basis @ bone.matrix
        matrix.translation *= 100
        edit[branches[bone.name]].matrix = matrix
    bpy.ops.object.mode_set(mode='OBJECT')
    export_fixture(calibration)
    report = {'purpose': 'Editor import probe, no game package.', 'fbx': str(path), 'native_bones': len(rest),
              'cc0_bones': len(branches), 'body_sha256': original, 'rotation_mapping': calibrations,
              'calibration_fbx': str(calibration), 'neck_carrier': NECK_CARRIER, 'neck_head_share': .35,
              'bone_parents': {name: parent for name, (parent, _) in new_rest.items()}}
    (output / 'bridge_probe.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('BAIQI_BRIDGE_PROBE_EXPORTED', len(rest), len(branches))


if __name__ == '__main__':
    main()
