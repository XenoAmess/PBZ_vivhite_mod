"""Import the combined-rig fixture into an isolated editor content path."""
import json
import math
from pathlib import Path

import unreal


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/baiqi_bridge_pose_probe'
data = json.loads((OUT / 'bridge_probe.json').read_text(encoding='utf-8'))
source = json.loads((ROOT / 'repro/game_reference/adult_reference.skel.json').read_text(encoding='utf-8'))['bones']
native = {bone['name']: bone for bone in source}
assert len(native) == data['native_bones'] == 264

FOLDER = '/Game/BaiQiBridgeProbe'
assets = unreal.AssetToolsHelpers.get_asset_tools()
asset_library = unreal.EditorAssetLibrary


def import_mesh(filename, name, folder=FOLDER, skeleton=None):
    options = unreal.FbxImportUI()
    for key, value in {
        'import_mesh': True, 'import_as_skeletal': True, 'import_materials': False, 'import_textures': False,
        'import_animations': False, 'create_physics_asset': False, 'automated_import_should_detect_type': False,
        'mesh_type_to_import': unreal.FBXImportType.FBXIT_SKELETAL_MESH,
    }.items():
        options.set_editor_property(key, value)
    if skeleton:
        options.set_editor_property('skeleton', skeleton)
    mesh_info = options.get_editor_property('skeletal_mesh_import_data')
    for key, value in {'convert_scene': True, 'force_front_x_axis': False, 'convert_scene_unit': False,
                       'import_morph_targets': False, 'update_skeleton_reference_pose': False}.items():
        mesh_info.set_editor_property(key, value)
    task = unreal.AssetImportTask()
    task.filename = filename
    task.destination_path = folder
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = False
    task.options = options
    task.factory = unreal.FbxFactory()
    assets.import_asset_tasks([task])
    result = unreal.load_asset(folder + '/' + name)
    assert isinstance(result, unreal.SkeletalMesh), name
    return result


def quaternion_product(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    result = (aw * bx + ax * bw + ay * bz - az * by,
              aw * by - ax * bz + ay * bw + az * bx,
              aw * bz + ax * by - ay * bx + az * bw,
              aw * bw - ax * bx - ay * by - az * bz)
    length = math.sqrt(sum(value * value for value in result))
    return [value / length for value in result]


def component_rotation(table):
    result = []
    for row in table:
        result.append(quaternion_product(result[row['parent']], row['q']) if row['parent'] >= 0 else row['q'])
    return {row['name']: rotation for row, rotation in zip(table, result)}


def local_offset(source_rotation, target_rotation):
    x, y, z, w = source_rotation
    return quaternion_product((-x, -y, -z, w), target_rotation)


tool = unreal.PBZModToolsLibrary


def reconcile_reference(mesh):
    imported_mesh = json.loads(tool.dump_ref_skeleton(mesh))
    assert len(imported_mesh) == len(data['bone_parents']), len(imported_mesh)
    actual_parents = {bone['name']: (imported_mesh[bone['parent']]['name'] if bone['parent'] >= 0 else None)
                      for bone in imported_mesh}
    assert actual_parents == data['bone_parents']

    # Calibrate the original driver side from its source ref-pose export. The
    # CC0 branch is imported in its own geometry basis and kept at that ref-pose.
    expected = [{**bone, **{key: native[bone['name']][key] for key in ('t', 'q', 's')}}
                if bone['name'] in native else bone for bone in imported_mesh]
    result = tool.apply_reference_pose(mesh, json.dumps({'bones': expected}))
    assert result.startswith('ok'), result
    readback = json.loads(tool.dump_ref_skeleton(mesh))
    for a, b in zip(expected, readback):
        assert a['name'] == b['name'] and a['parent'] == b['parent']
        for key in ('t', 's'):
            assert max(abs(x - y) for x, y in zip(a[key], b[key])) < .0002, (key, a['name'])
        assert abs(abs(sum(x * y for x, y in zip(a['q'], b['q']))) - 1.) < .00002, a['name']
    return readback


def bridge_steps(readback, calibration, follow_grip=False):
    driver = component_rotation(readback)
    target = component_rotation(calibration)
    steps = []
    for row in data['rotation_mapping']:
        a, b = row['source'], row['target']
        steps.append({'source': a, 'target': b, 'weight': 1., 'offset_xyzw': local_offset(driver[a], target[b])})
        if b.endswith('_Neck'):
            carrier = data['neck_carrier']
            steps.append({'source': 'head', 'target': carrier, 'weight': 1.,
                          'offset_xyzw': local_offset(driver['head'], target[b])})
            steps.append({'source': carrier, 'target': b, 'weight': data['neck_head_share']})
    if follow_grip:
        for side in ('l', 'r'):
            driver_hand = f'hand_{side}'
            visible_hand = f'BaiQi_J_Bip_{side.upper()}_Hand'
            steps.append({'source': visible_hand, 'target': driver_hand, 'weight': 1., 'copy_translation': True,
                          'offset_xyzw': local_offset(target[visible_hand], driver[driver_hand])})
    return steps


def attach_bridge(mesh, steps, blueprint_name, folder=FOLDER):
    blueprint_path = folder + '/' + blueprint_name
    skeleton = mesh.get_editor_property('skeleton')
    assert skeleton is not None
    asset_library.save_loaded_asset(skeleton)
    factory = unreal.AnimBlueprintFactory()
    factory.set_editor_property('target_skeleton', skeleton)
    blueprint = (unreal.load_asset(blueprint_path) if asset_library.does_asset_exist(blueprint_path)
                 else assets.create_asset(blueprint_name, folder, unreal.AnimBlueprint, factory))
    assert blueprint is not None
    if blueprint.get_editor_property('target_skeleton') != skeleton:
        blueprint.set_editor_property('target_skeleton', skeleton)
    compile_result = tool.build_bai_qi_bridge_graph(blueprint, json.dumps({'steps': steps}))
    assert compile_result.startswith('ok'), compile_result
    tool.set_post_process_anim_blueprint(mesh, blueprint.generated_class())
    asset_library.save_loaded_asset(blueprint)
    return blueprint_path


def main():
    mesh = import_mesh(data['fbx'], 'SK_BaiQiEditorBridgeFixture')
    asset_path = mesh.get_path_name()
    readback = reconcile_reference(mesh)
    asset_library.save_loaded_asset(mesh)
    calibrated_mesh = import_mesh(data['calibration_fbx'], 'SK_BaiQiBridgeCalibration')
    calibration = json.loads(tool.dump_ref_skeleton(calibrated_mesh))
    steps = bridge_steps(readback, calibration)
    (OUT / 'bridge_animgraph_steps.json').write_text(json.dumps({'steps': steps}, indent=2) + '\n', encoding='utf-8')
    blueprint_path = attach_bridge(mesh, steps, 'ABP_BaiQiEditorBridgeFixture')
    asset_library.save_loaded_asset(mesh)
    report = {'status': 'editor_skeleton_and_animgraph_verified', 'asset': asset_path, 'anim_graph': blueprint_path,
              'native_bones': data['native_bones'], 'cc0_bones': data['cc0_bones'],
              'body_sha256': data['body_sha256'], 'native_reference_transforms_verified': True,
              'cc0_reference_transforms_verified': True, 'bridge_steps': len(steps), 'game_package': False}
    (OUT / 'editor_bridge_readback.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    unreal.log('BAIQI_BRIDGE_PROBE_EDITOR_READBACK_OK')


if __name__ == '__main__':
    main()
