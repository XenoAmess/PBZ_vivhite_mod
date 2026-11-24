"""Export selected unmodified Adult Soul motion for the editor readback."""
import argparse
import json
from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tools/blender_libs'),
                str(ROOT / 'vendor/UEFormat/plugins/blender')]

from io_scene_ueformat.importer.import_context import UEFormatImport
from io_scene_ueformat.options import UEAnimOptions, UEModelOptions
from probe_baiqi_native_bridge import add_branch
from run_baiqi_cc0_motion_review import NATIVE_CLIPS, file_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / args.candidate))
    output = ROOT / args.out
    output.mkdir(parents=True, exist_ok=True)
    cc0 = bpy.data.objects['Armature']
    cc0.name = 'Original CC0 pose reference'
    previous = set(bpy.data.objects)
    UEFormatImport(UEModelOptions(scale_factor=1., reorient_bones=False, import_sockets=False,
                                  import_morph_targets=False)).import_file(ROOT / 'repro/game_reference/Hun_Body_Simple.uemodel')
    native = next(obj for obj in set(bpy.data.objects) - previous if obj.type == 'ARMATURE')
    native.name = 'Armature'
    add_branch(native, cc0)
    bpy.ops.object.select_all(action='DESELECT')
    native.select_set(True)
    bpy.context.view_layer.objects.active = native
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = .01
    manifest = []
    for name in NATIVE_CLIPS:
        source = ROOT / 'repro/game_reference/animations' / (name + '.ueanim')
        UEFormatImport(UEAnimOptions(scale_factor=1., override_skeleton=native, import_curves=False)).import_file(source)
        action = native.animation_data.action
        assert action
        scene.frame_start, scene.frame_end = [round(frame) for frame in action.frame_range]
        path = output / (name + '.fbx')
        bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, add_leaf_bones=False,
                                 use_mesh_modifiers=False, object_types={'ARMATURE'}, armature_nodetype='NULL',
                                 use_armature_deform_only=False, bake_anim=True, bake_anim_step=1.,
                                 bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False,
                                 bake_anim_simplify_factor=0.)
        manifest.append({'name': name, 'file': str(path), 'hash': file_hash(source),
                         'first_frame': scene.frame_start, 'last_frame': scene.frame_end})
    (output / 'native_motion_inputs.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
