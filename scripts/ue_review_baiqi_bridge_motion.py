"""Read back the actual engine-evaluated post-process pose in the editor."""
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import unreal


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from ue_probe_baiqi_native_bridge import (assets, asset_library, bridge_steps, data, import_mesh,
                                          quaternion_product, tool)


INPUT = ROOT / os.environ.get('PBZ_BAIQI_EDITOR_INPUTS', 'build/baiqi_054_game_inputs')


def import_motion(row, mesh, folder):
    name = 'AS_' + row['name']
    options = unreal.FbxImportUI()
    for key, value in {'import_mesh': False, 'import_as_skeletal': True, 'import_animations': True,
                       'import_materials': False, 'import_textures': False, 'create_physics_asset': False,
                       'automated_import_should_detect_type': False,
                       'mesh_type_to_import': unreal.FBXImportType.FBXIT_ANIMATION,
                       'skeleton': mesh.get_editor_property('skeleton')}.items():
        options.set_editor_property(key, value)
    info = options.get_editor_property('anim_sequence_import_data')
    info.set_editor_property('use_default_sample_rate', False)
    task = unreal.AssetImportTask()
    task.filename = row['file']
    task.destination_path = folder
    task.destination_name = name
    task.automated = task.replace_existing = True
    task.options = options
    task.save = False
    task.factory = unreal.FbxFactory()
    assets.import_asset_tasks([task])
    animation = unreal.load_asset(folder + '/' + name)
    assert isinstance(animation, unreal.AnimSequence), (folder, name)
    asset_library.save_loaded_asset(animation)
    return animation


def angular_error(a, b):
    dot = sum(x * y for x, y in zip(a, b)) / math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return math.degrees(2 * math.acos(min(1., abs(dot))))


def blend_rotation(a, b, fraction):
    dot = sum(x * y for x, y in zip(a, b))
    sign = 1 if dot >= 0 else -1
    values = [x * (1 - fraction) + y * fraction * sign for x, y in zip(a, b)]
    magnitude = math.sqrt(sum(value * value for value in values))
    return [value / magnitude for value in values]


def expected_rotations(pose, steps):
    rotations = {row['name']: row['q'] for row in pose}
    expected = {}
    for step in steps:
        source = rotations[step['source']]
        target = step['target']
        result = quaternion_product(source, step['offset_xyzw']) if 'offset_xyzw' in step else source
        if step['weight'] < 1.:
            result = blend_rotation(expected[target], result, step['weight'])
        expected[target] = rotations[target] = result
    return expected


def main():
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    level_path = '/Game/BaiQiBridgeProbe/BridgeAuditMap'
    level = levels.load_level(level_path) if asset_library.does_asset_exist(level_path) else levels.new_level(level_path)
    assert level, level_path
    forms = json.loads((INPUT / 'editor_form_readback.json').read_text(encoding='utf-8'))
    clips = json.loads((INPUT / 'native_motion/native_motion_inputs.json').read_text(encoding='utf-8'))
    calibration_asset = unreal.load_asset('/Game/BaiQiBridgeProbe/SK_BaiQiBridgeCalibration')
    if calibration_asset is None:
        calibration_asset = import_mesh(data['calibration_fbx'], 'SK_BaiQiBridgeCalibration')
        asset_library.save_loaded_asset(calibration_asset)
    calibration = json.loads(tool.dump_ref_skeleton(calibration_asset))
    result = {}
    for form, details in forms.items():
        mesh = unreal.load_asset(details['skeletal_mesh'])
        assert isinstance(mesh, unreal.SkeletalMesh)
        skeleton = json.loads(tool.dump_ref_skeleton(mesh))
        steps = bridge_steps(skeleton, calibration)
        folder = details['post_process'].rsplit('/', 1)[0] + '/AuditMotion'
        cases = []
        for clip in clips:
            animation = import_motion(clip, mesh, folder)
            samples = []
            for fraction in (0., .18, .25, .50, .75, 1.):
                raw = tool.sample_bai_qi_bridge_pose(mesh, animation, fraction)
                assert raw.startswith('['), raw
                pose = json.loads(raw)
                expected = expected_rotations(pose, steps)
                actual = {row['name']: row['q'] for row in pose}
                errors = {name: angular_error(actual[name], target) for name, target in expected.items()}
                worst = max(errors, key=errors.get)
                samples.append({'fraction': fraction, 'max_error_degrees': errors[worst], 'worst_joint': worst,
                                'neck_error_degrees': errors['BaiQi_J_Bip_C_Neck'],
                                'source_rotations': {name: actual[name] for name in ('head', 'pelvis', 'upperarm_l', 'lowerarm_l', 'thigh_l')}})
            motion = max(angular_error(rotation, samples[0]['source_rotations'][name]) for row in samples
                         for name, rotation in row['source_rotations'].items())
            assert motion > (1. if 'Idle' in clip['name'] else 15.), (form, clip['name'], motion)
            cases.append({'id': clip['name'], 'raw_clip_sha256': clip['hash'], 'samples': samples,
                          'source_motion_degrees': motion})
            unreal.log('BAIQI_EDITOR_POSE_READBACK ' + form + ' ' + clip['name'] + ' ' + str(max(s['max_error_degrees'] for s in samples)))
        result[form] = cases
    worst = max(sample['max_error_degrees'] for cases in result.values() for clip in cases for sample in clip['samples'])
    report = {'status': 'passed' if worst < 1.5 else 'failed', 'max_rotation_error_degrees': worst,
              'motion_source_sha256': hashlib.sha256((INPUT / 'native_motion/native_motion_inputs.json').read_bytes()).hexdigest(),
              'forms': result, 'game_launched': False}
    (INPUT / 'editor_motion_readback.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    assert worst < 1.5, worst


if __name__ == '__main__':
    main()
