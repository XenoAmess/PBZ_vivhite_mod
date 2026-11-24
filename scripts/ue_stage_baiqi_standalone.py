"""Author one BaiQi appearance and a saved coat toggle for PBZ Outfit Framework."""
import json
import os
from pathlib import Path
import sys

import unreal


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
os.environ.setdefault('PBZ_BAIQI_EDITOR_INPUTS', 'build/baiqi_standalone')

from ue_baiqi_native_materials import CLOTH, HAIR, PREFIX, build_native_palette
from ue_build_baiqi_forms import assign_materials, assets, skirt_collision, slug
from ue_probe_baiqi_native_bridge import asset_library, attach_bridge, bridge_steps, import_mesh, reconcile_reference, tool
from ue_stage_baiqi_adult_form import DRIVER_SKELETON, HUN, INPUT


FOLDER = '/HuaShira/Mods/BaiQi054/Standalone'
SLOT = 7351
OUTFIT = 'PBZ_OutFit_BaiQi'
TABLES = '/Game/Mods/PBZOutfitSlots'
SCHEMA = '/PBZModLoader/Options/S_PBZOutfitOption'
COAT_MATERIALS = {
    'BaiQi removable coat back', 'BaiQi gold-trimmed lapels',
    'BaiQi white sleeve cuffs', 'BaiQi gold cuff edging',
}


def save(asset):
    assert asset and asset_library.save_loaded_asset(asset), asset


def outfit_row(name, appearance_type, **fields):
    return dict(Name=name, ItemId=name, AppearanceType='EAppearanceType::' + appearance_type,
                bObtainableInGame=True, **fields)


def local_text(key, value):
    return dict(Namespace='Default', Key=f'{OUTFIT}_{key}', ValueCache=value)


def stage_body(prepared, mesh_path):
    if asset_library.does_asset_exist(mesh_path):
        existing = unreal.load_asset(mesh_path)
        if asset_library.get_metadata_tag(existing, 'BaiQiSourceHash') == prepared['source_sha256']:
            return existing
        raise RuntimeError(f'Clear the stale standalone editor mesh before rebuilding {mesh_path}')
    palette = build_native_palette()
    skeleton = unreal.load_asset(DRIVER_SKELETON)
    body = import_mesh(prepared['fbx'], 'SK_BaiQi', FOLDER, skeleton=skeleton)
    reference = reconcile_reference(body)
    names = assign_materials(body, palette)
    assert all(name.startswith('baiqiinvisibledriversection') for name in names[:18])
    assert len(reference) == 348 and body.get_editor_property('skeleton') == skeleton
    tool.set_mesh_physics_asset(body, unreal.load_asset(HUN + '/PA_Hun'))
    calibration = unreal.load_asset('/Game/BaiQiBridgeProbe/SK_BaiQiBridgeCalibration')
    calibration_bones = json.loads(tool.dump_ref_skeleton(calibration))
    attach_bridge(body, bridge_steps(reference, calibration_bones, follow_grip=True), 'ABP_AdultBaiQi', FOLDER)
    skirt_collision(body, reference, FOLDER + '/Cloth', prepared['skirt_leg_support'])
    for name in ('BaiQi bob front appearance', 'BaiQi side hair source color',
                 'BaiQi black gold headdress appearance', 'BaiQi round gold glasses appearance'):
        assert tool.set_section_cast_shadow(body, name, False) > 0, name
    asset_library.set_metadata_tag(body, 'BaiQiSourceHash', prepared['source_sha256'])
    save(body)
    return body


def stage_blank(hidden_slot):
    path = FOLDER + '/SK_BaiQiBlank'
    if asset_library.does_asset_exist(path):
        return unreal.load_asset(path)
    source = HUN + '/SkinParts/Hun_Head_New'
    blank = asset_library.duplicate_asset(source, path)
    assert isinstance(blank, unreal.SkeletalMesh), source
    slots = blank.get_editor_property('materials')
    for slot in slots:
        slot.set_editor_property('material_interface', hidden_slot)
    blank.set_editor_property('materials', slots)
    save(blank)
    return blank


def stage_icon():
    icon = FOLDER + '/T_BaiQiAppearance'
    if not asset_library.does_asset_exist(icon):
        task = unreal.AssetImportTask()
        task.filename = str(INPUT / 'appearance_icon.png')
        task.destination_path = FOLDER
        task.destination_name = 'T_BaiQiAppearance'
        task.automated = True
        task.save = True
        task.factory = unreal.TextureFactory()
        assets.import_asset_tasks([task])
    texture = unreal.load_asset(icon)
    assert isinstance(texture, unreal.Texture2D), icon
    return texture


def main():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    forms = json.loads((INPUT / 'form_inputs.json').read_text(encoding='utf-8'))
    prepared = forms['coat_on']
    assert prepared['body_sha256'] == forms['coat_off']['body_sha256']
    palette_specs = json.loads((INPUT / 'engine_materials.json').read_text(encoding='utf-8'))
    assert COAT_MATERIALS <= palette_specs.keys()
    body = stage_body(prepared, FOLDER + '/SK_BaiQi')
    slots = body.get_editor_property('materials')
    names = [str(slot.get_editor_property('material_slot_name')) for slot in slots]
    coat_names = {slug(name) for name in COAT_MATERIALS}
    coat_slots = [index for index, name in enumerate(names) if slug(name) in coat_names]
    assert len(coat_slots) == len(coat_names) and min(coat_slots) >= 18, names
    blank = stage_blank(slots[0].get_editor_property('material_interface'))
    icon = stage_icon()
    body_id, hair_id, band_id, brow_id = [f'BaiQi_{name}' for name in ('Body', 'Hair', 'Band', 'Brow')]
    outfit_table = f'{TABLES}/DT_OutfitSlot_{SLOT}'
    options_table = f'{TABLES}/DT_OptionsSlot_{SLOT}'
    schema = json.loads((INPUT / 'option_schema.json').read_text(encoding='utf-8'))
    config = dict(schema, mesh=body.get_path_name(), outfit_table=outfit_table, options_table=options_table,
                  coat_slots=coat_slots, option_label='脱外套', appearance_rows=[
                      outfit_row(OUTFIT, 'Outfit', AppearanceName=local_text('Name', '白绮'),
                                 AppearanceDesc=local_text('Desc', '白绮，可穿脱外套。'),
                                 AppearanceTexture=icon.get_path_name(), OutfitBodyItem=body_id,
                                 OutfitHairStyleItem=hair_id, OutfitSequenceHairStyleItem=hair_id,
                                 OutfitMeshBandItem=band_id, OutfitBrowLashCardItem=brow_id, bDefaultHatHidden=True),
                      outfit_row(body_id, 'Body', BodyMeshAsset=body.get_path_name()),
                      outfit_row(hair_id, 'Hairstyle', HeadAsset=blank.get_path_name()),
                      outfit_row(band_id, 'MeshBand', MeshBandAsset=blank.get_path_name()),
                      outfit_row(brow_id, 'BrowLashCard', BrowLashCardAsset=blank.get_path_name()),
                  ])
    result = tool.build_bai_qi_outfit_tables(json.dumps(config, ensure_ascii=False))
    assert result == 'ok appearance=5 options=1', result
    for path in (SCHEMA, outfit_table, options_table):
        save(unreal.load_asset(path))
    asset_paths = [outfit_table, options_table]
    for folder in (FOLDER, PREFIX):
        asset_paths.extend(asset.split('.')[0] for asset in asset_library.list_assets(folder, recursive=True))
    report = dict(
        status='staged_pending_cook', form='standalone', adult_bones=264, combined_bones=348,
        source_sha256=prepared['source_sha256'], body_sha256=prepared['body_sha256'], replacement_packages=[],
        excluded_placeholders=[SCHEMA, DRIVER_SKELETON, HUN + '/PA_Hun', CLOTH, HAIR],
        owned_assets=sorted(set(asset_paths)), outfit_id=OUTFIT, framework_slot=SLOT,
        coat_slots={index: names[index] for index in coat_slots}, default_coat_visible=True,
    )
    (INPUT / 'standalone_allowlist.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    unreal.log('BAIQI_STANDALONE_STAGED ' + result)


if __name__ == '__main__':
    main()
