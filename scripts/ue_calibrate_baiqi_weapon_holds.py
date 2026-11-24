"""Update the native weapon attachment wrist positions after the visible pose."""
import json
import math
import os
from pathlib import Path
import sys

import unreal


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from ue_stage_baiqi_adult_form import BODY_PACKAGES, INPUT
from ue_probe_baiqi_native_bridge import asset_library, attach_bridge, bridge_steps, tool
from ue_review_baiqi_bridge_motion import import_motion


def main():
    form = os.environ['PBZ_BAIQI_FORM']
    assert form in {'coat_on', 'coat_off'}
    unreal.AssetRegistryHelpers.get_asset_registry().search_all_assets(True)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert levels.load_level('/Game/BaiQiBridgeProbe/BridgeAuditMap')
    calibration_mesh = unreal.load_asset('/Game/BaiQiBridgeProbe/SK_BaiQiBridgeCalibration')
    calibration = json.loads(tool.dump_ref_skeleton(calibration_mesh))
    own = '/HuaShira/Mods/BaiQi054/' + form
    body = unreal.load_asset(BODY_PACKAGES[0])
    skeleton = json.loads(tool.dump_ref_skeleton(body))
    steps = bridge_steps(skeleton, calibration, follow_grip=True)
    graph = attach_bridge(body, steps, 'ABP_AdultBaiQi', own)
    assert asset_library.save_loaded_asset(body)

    motion = ROOT / 'build/baiqi_054_game_inputs/native_motion/native_motion_inputs.json'
    clips = json.loads(motion.read_text(encoding='utf-8'))
    results = []
    for clip in clips:
        animation = import_motion(clip, body, '/Game/BaiQiBridgeProbe/GripAudit')
        for fraction in (0., .25, .50, .75):
            pose = json.loads(tool.sample_bai_qi_bridge_pose(body, animation, fraction))
            bones = {row['name']: row for row in pose}
            wrist_error = {}
            for side in ('l', 'r'):
                visible = bones[f'BaiQi_J_Bip_{side.upper()}_Hand']['t']
                stock = bones[f'hand_{side}']['t']
                wrist_error[side] = math.dist(visible, stock)
            assert max(wrist_error.values()) < .05, (clip['name'], fraction, wrist_error)
            results.append({'clip': clip['name'], 'fraction': fraction, 'wrist_error_cm': wrist_error})
    for path in BODY_PACKAGES[1:]:
        mesh = unreal.load_asset(path)
        tool.set_post_process_anim_blueprint(mesh, unreal.load_asset(graph).generated_class())
        assert asset_library.save_loaded_asset(mesh)
    (INPUT / f'{form}_grip_alignment.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    unreal.log('BAIQI_WEAPON_WRISTS_ALIGNED ' + form)


if __name__ == '__main__':
    main()
