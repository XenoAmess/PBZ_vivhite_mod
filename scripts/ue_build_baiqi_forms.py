"""Assemble the two editor preview assets with baked materials and skirt collision."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

import unreal


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from ue_probe_baiqi_native_bridge import (assets, asset_library, attach_bridge, bridge_steps,
                                          data, import_mesh, reconcile_reference, tool)


INPUT = ROOT / os.environ.get('PBZ_BAIQI_EDITOR_INPUTS', 'build/baiqi_054_game_inputs')
PREVIEW = os.environ.get('PBZ_BAIQI_CONTENT_ROOT', '/Game/BaiQiBridgeProbe/' + INPUT.name)
MEL = unreal.MaterialEditingLibrary


def slug(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())


def cached_asset(folder, name, kind, factory):
    path = folder + '/' + name
    return unreal.load_asset(path) if asset_library.does_asset_exist(path) else assets.create_asset(name, folder, kind, factory)


def texture(path):
    folder = PREVIEW + '/Textures'
    name = path.stem
    location = folder + '/' + name
    if asset_library.does_asset_exist(location):
        return unreal.load_asset(location)
    task = unreal.AssetImportTask()
    task.filename = str(path)
    task.destination_path = folder
    task.destination_name = name
    task.automated = True
    task.save = False
    task.factory = unreal.TextureFactory()
    assets.import_asset_tasks([task])
    result = unreal.load_asset(location)
    assert isinstance(result, unreal.Texture2D), location
    result.set_editor_property('srgb', True)
    asset_library.save_loaded_asset(result)
    return result


def build_material(name, spec):
    identifier = 'M_BaiQi_' + hashlib.sha256(name.encode('utf-8')).hexdigest()[:14]
    material = cached_asset(PREVIEW + '/Materials', identifier, unreal.Material, unreal.MaterialFactoryNew())
    MEL.delete_all_material_expressions(material)
    kind = spec['type']
    unlit = kind.startswith('skin_') or kind == 'hidden'
    masked = kind in {'masked', 'hidden', 'skin_junction'}
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT if unlit
                                 else unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED if masked else unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property('two_sided', masked or 'skirt' in name.lower())
    material.set_editor_property('opacity_mask_clip_value', .12 if kind == 'skin_junction' else .25)
    emissive = unreal.MaterialProperty.MP_EMISSIVE_COLOR if unlit else unreal.MaterialProperty.MP_BASE_COLOR
    if spec['texture']:
        node = MEL.create_material_expression(material, unreal.MaterialExpressionTextureSample, -450, 0)
        node.set_editor_property('texture', texture(INPUT / spec['texture']))
        MEL.connect_material_property(node, 'RGB', emissive)
        if masked:
            MEL.connect_material_property(node, 'A', unreal.MaterialProperty.MP_OPACITY_MASK)
    elif kind == 'skin_junction':
        node = MEL.create_material_expression(material, unreal.MaterialExpressionVertexColor, -450, 0)
        MEL.connect_material_property(node, 'RGB', emissive)
        MEL.connect_material_property(node, 'A', unreal.MaterialProperty.MP_OPACITY_MASK)
    else:
        node = MEL.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, -450, 0)
        node.set_editor_property('constant', unreal.LinearColor(*spec['color']))
        MEL.connect_material_property(node, '', emissive)
        if kind == 'hidden':
            opacity = MEL.create_material_expression(material, unreal.MaterialExpressionConstant, -450, 180)
            opacity.set_editor_property('r', 0.)
            MEL.connect_material_property(opacity, '', unreal.MaterialProperty.MP_OPACITY_MASK)
    if not unlit:
        roughness = MEL.create_material_expression(material, unreal.MaterialExpressionConstant, -450, 360)
        roughness.set_editor_property('r', .81)
        MEL.connect_material_property(roughness, '', unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(material)
    asset_library.save_loaded_asset(material)
    return material


def assign_materials(mesh, materials):
    slots = []
    names = []
    for slot in mesh.get_editor_property('materials'):
        name = slug(str(slot.get_editor_property('material_slot_name')))
        slot.set_editor_property('material_interface', materials[name])
        slots.append(slot)
        names.append(name)
    mesh.set_editor_property('materials', slots)
    saved = mesh.get_editor_property('materials')
    assert [slot.get_editor_property('material_interface') for slot in saved] == [materials[name] for name in names]
    return names


def skirt_collision(mesh, skeleton, folder, supported=False):
    bones = {row['name']: row for row in skeleton}
    bodies = []
    for side in ('L', 'R'):
        thigh = f'BaiQi_J_Bip_{side}_UpperLeg'
        direction = bones[f'BaiQi_J_Bip_{side}_LowerLeg']['t']
        length = math.sqrt(sum(value * value for value in direction))
        orientation = unreal.MathLibrary.make_rot_from_z(unreal.Vector(*direction))
        capsules = [(0.26, 6.1, .27), (.60, 5.1, .25)] if supported else [(0.21, 6.7, .29), (.60, 5.6, .27)]
        for position, radius, proportion in capsules:
            bodies.append({'bone': thigh, 'type': 'capsule', 'radius': radius, 'length': length * proportion,
                           'center': [value * position for value in direction],
                           'rotation': [orientation.pitch, orientation.yaw, orientation.roll], 'kinematic': True})
    collider = tool.create_physics_asset(folder, 'PH_BaiQiClothThighs', mesh)
    result = tool.build_physics_asset(collider, mesh, json.dumps({'bodies': bodies}))
    assert result.startswith('ok'), result
    asset_library.save_loaded_asset(collider)

    slots = mesh.get_editor_property('materials')
    skirt = next(str(slot.get_editor_property('material_slot_name')) for slot in slots
                 if 'pleatedskirtartwork' in slug(str(slot.get_editor_property('material_slot_name'))))
    mask = {'type': 'plane', 'anchors': [[0, 0, 100]], 'dir': [0, 0, -1], 'd0': 1.9, 'd1': 19.0}
    travel = 9.5 if supported else 32.
    result = tool.create_cloth_from_slot(mesh, skirt, 'BaiQiSkirt', collider, travel, json.dumps(mask), '{}')
    assert result.startswith('ok'), result
    assert tool.set_cloth_solver(mesh, 10, 3) >= 1
    return result


def main():
    sources = json.loads((INPUT / 'form_inputs.json').read_text(encoding='utf-8'))
    specs = json.loads((INPUT / 'engine_materials.json').read_text(encoding='utf-8'))
    materials = {slug(name): build_material(name, value) for name, value in specs.items()}
    calibrated = import_mesh(data['calibration_fbx'], 'SK_BaiQiBridgeCalibration')
    asset_library.save_loaded_asset(calibrated.get_editor_property('skeleton'))
    asset_library.save_loaded_asset(calibrated)
    calibration = json.loads(tool.dump_ref_skeleton(calibrated))
    results = {}
    for form, source in sources.items():
        name = 'WithCoat' if form == 'coat_on' else 'WithoutCoat'
        folder = PREVIEW + '/' + name
        mesh = import_mesh(source['fbx'], 'SK_BaiQi_' + name, folder)
        skeleton = reconcile_reference(mesh)
        names = assign_materials(mesh, materials)
        graph = attach_bridge(mesh, bridge_steps(skeleton, calibration), 'ABP_BaiQi_' + name, folder)
        cloth = skirt_collision(mesh, skeleton, folder)
        asset_library.save_loaded_asset(mesh)
        results[form] = {'skeletal_mesh': mesh.get_path_name(), 'post_process': graph, 'material_slots': len(names),
                         'reference_bones': len(skeleton), 'cloth_binding': cloth, 'source_sha256': source['source_sha256']}
        unreal.log('BAIQI_EDITOR_FORM_READY ' + form)
    (INPUT / 'editor_form_readback.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
