"""Stage one 054 form at the verified Adult Soul replacement package paths."""
import json
import os
from pathlib import Path
import sys

import unreal


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
os.environ['PBZ_BAIQI_CONTENT_ROOT'] = '/HuaShira/Mods/BaiQi054/Shared'

from ue_build_baiqi_forms import assign_materials, build_material, skirt_collision, slug
from ue_probe_baiqi_native_bridge import asset_library, attach_bridge, bridge_steps, import_mesh, reconcile_reference, tool


INPUT = ROOT / 'build/baiqi_054_package_inputs'
HUN = '/HuaShira/Characters/Hero/Hero_Hun'
DRIVER_SKELETON = HUN + '/Hun_Skin_Skeleton'
BODY_PACKAGES = [HUN + '/SkinParts/Hun_Body_Simple',
                 '/HuaShira/Characters/Hero/Hero_Hun_Climax/SkinParts/Hun_Body_Climax',
                 '/HuaShira/Characters/Hero/Hero_Hun_MoTian/Hun_MoTian_Body_Simple']


def main():
    form = os.environ['PBZ_BAIQI_FORM']
    assert form in {'coat_on', 'coat_off'}
    assert os.environ.get('PBZ_BAIQI_EDITOR_INPUTS') == 'build/baiqi_054_package_inputs'
    prepared = json.loads((INPUT / 'form_inputs.json').read_text(encoding='utf-8'))[form]
    assert prepared['reserved_native_slots'] == 18 and prepared['native_bones'] == 264
    editor_audit = json.loads((ROOT / 'build/baiqi_054_game_inputs/editor_motion_readback.json').read_text(encoding='utf-8'))
    assert editor_audit['status'] == 'passed'
    assert all(clip.get('source_motion_degrees', 0) > 1 for clip in editor_audit['forms'][form])
    legacy = json.loads((ROOT / 'build/reports/editor_import.json').read_text(encoding='utf-8'))
    assert set(BODY_PACKAGES).issubset(legacy['replacement_packages'])
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.scan_paths_synchronous(['/HuaShira/Mods', '/Game/BaiQiBridgeProbe'], False)
    source_skeleton = unreal.load_asset(DRIVER_SKELETON)
    assert isinstance(source_skeleton, unreal.Skeleton)
    source_physics = unreal.load_asset(HUN + '/PA_Hun')
    palette = json.loads((INPUT / 'engine_materials.json').read_text(encoding='utf-8'))
    materials = {slug(name): build_material(name, spec) for name, spec in palette.items()}
    camera = unreal.load_asset('/Game/BaiQiBridgeProbe/SK_BaiQiBridgeCalibration')
    calibration = json.loads(tool.dump_ref_skeleton(camera))
    own = '/HuaShira/Mods/BaiQi054/' + form
    graph_name = 'ABP_AdultBaiQi'
    graph = None
    staged = []
    for index, path in enumerate(BODY_PACKAGES):
        folder, name = path.rsplit('/', 1)
        mesh = import_mesh(prepared['fbx'], name, folder, skeleton=source_skeleton)
        assert mesh.get_editor_property('skeleton').get_path_name().split('.')[0] == DRIVER_SKELETON
        reference = reconcile_reference(mesh)
        names = assign_materials(mesh, materials)
        assert len(names) >= 18 and all(name.startswith('baiqiinvisibledriversection') for name in names[:18]), names
        if source_physics:
            tool.set_mesh_physics_asset(mesh, source_physics)
        if graph is None:
            graph = attach_bridge(mesh, bridge_steps(reference, calibration), graph_name, own)
        else:
            tool.set_post_process_anim_blueprint(mesh, unreal.load_asset(graph).generated_class())
        cloth = skirt_collision(mesh, reference, own + '/Cloth_' + str(index))
        asset_library.save_loaded_asset(mesh)
        staged.append({'path': path, 'slot_count': len(names), 'cloth': cloth})
    owners = [own, os.environ['PBZ_BAIQI_CONTENT_ROOT'], '/HuaShira/Mods/DeltaLive2D']
    owned_assets = []
    for folder in owners:
        if asset_library.does_directory_exist(folder):
            owned_assets.extend(item.split('.')[0] for item in asset_library.list_assets(folder, recursive=True, include_folder=False))
    assert graph in owned_assets
    report = {'adult_bones': 264, 'combined_bones': 348, 'form': form,
              'source_sha256': prepared['source_sha256'], 'body_sha256': prepared['body_sha256'],
              'replacement_packages': legacy['replacement_packages'], 'excluded_placeholders': legacy['excluded_placeholders'],
              'owned_assets': sorted(set(owned_assets)), 'staged_bodies': staged, 'status': 'staged_pending_cook'}
    (INPUT / f'{form}_allowlist.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    unreal.log('BAIQI_ADULT_FORM_STAGED ' + form)


if __name__ == '__main__':
    main()
