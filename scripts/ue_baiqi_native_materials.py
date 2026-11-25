"""Assign shipped cloth and cutout shader parents to the BaiQi cooked meshes."""
import hashlib
import json
import os
from pathlib import Path
import sys

import unreal


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ue_stage_baiqi_adult_form import INPUT, BODY_PACKAGES, assign_materials
from ue_build_baiqi_forms import asset_library, assets, cached_asset, slug, tool


PREFIX = os.environ.get('PBZ_BAIQI_NATIVE_PREFIX', '/HuaShira/Mods/BaiQi054/Shared/Native')
STOCK = '/Game/PBZContent/Characters/Hero/Hun_New_V2b/Material/'
CLOTH = STOCK + 'MI_ZeroHun_Cloth_02_b'
HAIR = STOCK + 'Hun_Status/MI_ZeroHun_HairCard_Health'
MEL = unreal.MaterialEditingLibrary


def texture(name, *, normal=False, linear=False):
    folder = PREFIX + '/Textures'
    path = folder + '/' + name
    image = unreal.load_asset(path) if asset_library.does_asset_exist(path) else None
    if image is None:
        task = unreal.AssetImportTask()
        task.filename = str(INPUT / 'native_textures' / (name + '.png'))
        task.destination_path = folder
        task.destination_name = name
        task.automated = True
        task.save = False
        task.factory = unreal.TextureFactory()
        assets.import_asset_tasks([task])
        image = unreal.load_asset(path)
    assert isinstance(image, unreal.Texture2D), path
    image.set_editor_property('srgb', not (normal or linear))
    image.set_editor_property('compression_no_alpha', True)
    image.set_editor_property('power_of_two_mode', unreal.TexturePowerOfTwoSetting.NONE)
    image.set_editor_property('virtual_texture_streaming', True)
    if normal:
        image.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_NORMALMAP)
    elif linear:
        image.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_MASKS)
    asset_library.save_loaded_asset(image)
    return image


def instance(name, kind, parents, neutral, finish):
    stem = hashlib.sha256(name.encode()).hexdigest()[:14]
    material = cached_asset(PREFIX + '/Materials', 'MI_BaiQi_' + stem, unreal.MaterialInstanceConstant,
                            unreal.MaterialInstanceConstantFactoryNew())
    masked = kind in {'hidden', 'masked'}
    MEL.set_material_instance_parent(material, parents['hair' if masked else 'cloth'])
    tool.clear_material_instance_parameters(material)
    albedo = texture('T_BaiQiNative_' + stem)
    if masked:
        mask = texture('T_BaiQiAlpha_' + stem, linear=True)
        for parameter, value in [('Diffuse', albedo), ('Alpha', mask), ('Depth', neutral['white']),
                                 ('Root', neutral['white']), ('Unique_Hair_Value', neutral['black']),
                                 ('HairAO', neutral['white']), ('Normal_map', neutral['normal']),
                                 ('FlowMapTexture', neutral['normal'])]:
            tool.set_material_texture_parameter(material, parameter, 0, -1, value)
        for parameter, value in [('Brightness', 1.), ('RandomHueVariation', 0.), ('RandomValueVariation', 0.),
                                 ('HairAOStrength', 0.), ('Roughness', .85), ('Specular', .08),
                                 ('NormalStrength', 0.), ('RootDitherRange', 0.), ('UseDither', 0.),
                                 ('Dissolve_ExtraDissolve', 0.)]:
            tool.set_material_scalar_parameter(material, parameter, 0, -1, value)
        for parameter in ('RootColor', 'TipColor'):
            tool.set_material_vector_parameter(material, parameter, 0, -1, unreal.LinearColor(1., 1., 1., 1.))
    else:
        normal = texture(finish['normal'], normal=True) if 'normal' in finish else neutral['normal']
        mix = texture(finish['mix'], linear=True) if 'mix' in finish else neutral['mix']
        normal_strength = finish.get('normal_strength', 0.)
        for parameter, value in [('Albedo', albedo), ('Normal', normal), ('Mix', mix)]:
            tool.set_material_texture_parameter(material, parameter, 1, 0, value)
        for parameter, value in [('NormalIntensity', normal_strength), ('BaseColor Intensity', 1.),
                                 ('Normal Strength', normal_strength), ('ClothFuzzIntensity', 0.),
                                 ('ClothIntensity', 0.), ('Specular', finish.get('specular', .15))]:
            tool.set_material_scalar_parameter(material, parameter, 1, 0, value)
        tool.set_material_scalar_parameter(material, 'NormalIntensity', 1, 1, 0.)
        tool.set_material_scalar_parameter(material, 'Roughness Overlay Intensity', 1, 1, 0.)
        tool.set_material_scalar_parameter(material, 'FuzzIntensity', 2, 0, 0.)
        for parameter in ('Wetness Min', 'Wetness Max', 'RainDrops | StaticDrops Intensity', 'RainDrops | DrippingDrop Intensity'):
            tool.set_material_scalar_parameter(material, parameter, 0, -1, 0.)
    MEL.update_material_instance(material)
    asset_library.save_loaded_asset(material)
    return material


def build_native_palette():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    cloth = unreal.load_asset(CLOTH)
    assert isinstance(cloth, unreal.MaterialInstanceConstant)
    parent = cached_asset(*HAIR.rsplit('/', 1), unreal.MaterialInstanceConstant,
                          unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(parent, cloth.get_editor_property('parent'))
    asset_library.save_loaded_asset(parent)
    neutral = {'normal': texture('T_BaiQiNative_FlatNormal', normal=True),
               'mix': texture('T_BaiQiNative_Mix', linear=True),
               'white': texture('T_BaiQiNative_NeutralWhite', linear=True),
               'black': texture('T_BaiQiNative_NeutralBlack', linear=True)}
    model = json.loads((INPUT / 'engine_materials.json').read_text(encoding='utf-8'))
    path = INPUT / 'surface_finish.json'
    finishes = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    assert set(finishes) <= model.keys(), set(finishes) - model.keys()
    parents = {'cloth': cloth, 'hair': parent}
    return {slug(name): instance(name, row['type'], parents, neutral, finishes.get(name, {}))
            for name, row in model.items()}


def main():
    form = os.environ['PBZ_BAIQI_FORM']
    assert form in {'coat_on', 'coat_off'}
    palette = build_native_palette()
    for path in BODY_PACKAGES:
        mesh = unreal.load_asset(path)
        assign_materials(mesh, palette)
        for name in ('BaiQi bob front appearance', 'BaiQi side hair source color',
                     'BaiQi black gold headdress appearance', 'BaiQi round gold glasses appearance'):
            assert tool.set_section_cast_shadow(mesh, name, False) > 0, (path, name)
        assert asset_library.save_loaded_asset(mesh)
    path = INPUT / f'{form}_allowlist.json'
    allow = json.loads(path.read_text(encoding='utf-8'))
    payload = [name for name in allow['owned_assets'] if not name.startswith(PREFIX.rsplit('/', 1)[0] + '/')]
    payload.extend(name.split('.')[0] for name in asset_library.list_assets(PREFIX, recursive=True))
    allow['owned_assets'] = sorted(set(payload))
    allow['excluded_placeholders'] = sorted(set(allow['excluded_placeholders'] + [CLOTH, HAIR]))
    allow['material_strategy'] = 'native_baiqi_cloth_and_cutout'
    path.write_text(json.dumps(allow, indent=2) + '\n', encoding='utf-8')
    unreal.log('BAIQI_NATIVE_MATERIALS_BOUND ' + form)


if __name__ == '__main__':
    main()
