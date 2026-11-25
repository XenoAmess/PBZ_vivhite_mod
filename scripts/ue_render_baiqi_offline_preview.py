"""Render imported BaiQi meshes with their archived maps in a local Unreal preview scene."""
import hashlib
from functools import lru_cache
import json
import os
from pathlib import Path
import re

import unreal


ROOT = Path(__file__).resolve().parents[1]
CONTENT = '/Game/BaiQiBridgeProbe/OfflinePreview'
FORMS = ('coat_on', 'coat_off')
FACE = 'BaiQi original face appearance'
SHOTS = {
    'front_left': ((0., 1., 0.), -54.),
    'front_right': ((0., 1., 0.), -126.),
    'oblique': ((-.43, .903, .06), -44.),
    'rear_high': ((-.24, -.93, .28), 56.),
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def compact(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())


def stem(name):
    return hashlib.sha256(name.encode()).hexdigest()[:14]


ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
EDIT = unreal.MaterialEditingLibrary
RENDER = unreal.RenderingLibrary
V = unreal.Vector


@lru_cache(maxsize=None)
def texture(inputs, name, kind):
    source = inputs / 'native_textures' / f'{name}.png'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
    asset_name = f'{name}_{source_hash}'
    # Session textures resolve their pixel data immediately in commandlet captures.
    folder = CONTENT + '/Session/Textures'
    path = f'{folder}/{asset_name}'
    task = unreal.AssetImportTask()
    task.filename = str(source)
    task.destination_path = folder
    task.destination_name = asset_name
    task.automated = True
    task.save = False
    task.factory = unreal.TextureFactory()
    ASSETS.import_asset_tasks([task])
    result = unreal.load_asset(path)
    assert isinstance(result, unreal.Texture2D), path
    result.set_editor_property('srgb', kind == 'color')
    result.set_editor_property('virtual_texture_streaming', False)
    result.set_editor_property('never_stream', True)
    if kind != 'color':
        settings = unreal.TextureCompressionSettings
        result.set_editor_property('compression_settings', settings.TC_NORMALMAP if kind == 'normal' else settings.TC_MASKS)
    return result


def preview_parent(inputs, masked):
    name = 'M_BaiQiOfflineMasked' if masked else 'M_BaiQiOfflineOpaque'
    folder = CONTENT + '/Session'
    _, name = ASSETS.create_unique_asset_name(f'{folder}/{name}', '')
    material = ASSETS.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    material.set_editor_property('two_sided', True)
    material.set_editor_property('used_with_skeletal_mesh', True)
    sampler = unreal.MaterialSamplerType
    properties = unreal.MaterialProperty

    def sample(name, default, kind, position):
        node = EDIT.create_material_expression(material, unreal.MaterialExpressionTextureSampleParameter2D, *position)
        node.set_editor_property('parameter_name', name)
        node.set_editor_property('texture', texture(inputs, default, kind))
        types = {'color': sampler.SAMPLERTYPE_COLOR, 'normal': sampler.SAMPLERTYPE_NORMAL, 'masks': sampler.SAMPLERTYPE_MASKS}
        node.set_editor_property('sampler_type', types[kind])
        return node

    albedo = sample('Albedo', f'T_BaiQiNative_{stem(FACE)}', 'color', (-450, 0))
    mix = sample('Mix', 'T_BaiQiNative_Mix', 'masks', (-450, 150))
    normals = sample('Normals', 'T_BaiQiNative_FlatNormal', 'normal', (-620, 340))
    assert EDIT.connect_material_property(albedo, 'RGB', properties.MP_BASE_COLOR)
    for channel, prop in [('R', properties.MP_AMBIENT_OCCLUSION), ('G', properties.MP_ROUGHNESS), ('B', properties.MP_METALLIC)]:
        assert EDIT.connect_material_property(mix, channel, prop)
    specular = EDIT.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -190, 180)
    specular.set_editor_property('parameter_name', 'Specular')
    specular.set_editor_property('default_value', .19)
    assert EDIT.connect_material_property(specular, '', properties.MP_SPECULAR)
    strength = EDIT.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -620, 450)
    strength.set_editor_property('parameter_name', 'NormalStrength')
    strength.set_editor_property('default_value', 0.)
    forward = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, -620, 530)
    forward.set_editor_property('constant', unreal.LinearColor(0., 0., 1., 1.))
    blend = EDIT.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate, -220, 390)
    for expression, pin in [(forward, 'A'), (normals, 'B'), (strength, 'Alpha')]:
        assert EDIT.connect_material_expressions(expression, '', blend, pin)
    assert EDIT.connect_material_property(blend, '', properties.MP_NORMAL)
    if masked:
        material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
        alpha = sample('Opacity', 'T_BaiQiNative_NeutralWhite', 'masks', (-460, 640))
        assert EDIT.connect_material_property(alpha, 'R', properties.MP_OPACITY_MASK)
    EDIT.recompile_material(material)
    return material


def apply_maps(inputs, instance, name, spec, finish):
    maps = [('Albedo', f'T_BaiQiNative_{stem(name)}', 'color'),
            ('Mix', finish.get('mix', 'T_BaiQiNative_Mix'), 'masks'),
            ('Normals', finish.get('normal', 'T_BaiQiNative_FlatNormal'), 'normal')]
    if spec['type'] in ('masked', 'hidden'):
        maps.append(('Opacity', f'T_BaiQiAlpha_{stem(name)}', 'masks'))
    for parameter, image, kind in maps:
        expected = texture(inputs, image, kind)
        instance.set_texture_parameter_value(parameter, expected)
        assert instance.get_texture_parameter_value(parameter) == expected, (name, parameter)
    for parameter, value in [('Specular', finish.get('specular', .15)), ('NormalStrength', finish.get('normal_strength', 0.))]:
        instance.set_scalar_parameter_value(parameter, value)
        assert abs(instance.get_scalar_parameter_value(parameter) - value) < 1e-6, (name, parameter)


def confirm_color(world, target, form):
    regions = {'face': ((220, 350), (250, 380), (390, 370), (422, 345), (320, 500), (260, 480)),
               'head ornament': ((94, 255), (94, 275), (94, 315), (94, 375), (112, 295), (148, 355))}
    for name, points in regions.items():
        readings = [RENDER.read_render_target_raw_pixel(world, target, x, y) for x, y in points]
        assert any(max(pixel.r, pixel.g, pixel.b) - min(pixel.r, pixel.g, pixel.b) > 10.
                   for pixel in readings), (form, name)


def main():
    inputs = ROOT / os.environ['PBZ_BAIQI_EDITOR_INPUTS']
    output = ROOT / os.environ['PBZ_BAIQI_PREVIEW_OUT']
    output.mkdir(parents=True, exist_ok=True)
    readback = read(inputs / 'surface_finish_readback.json')
    materials = read(inputs / 'engine_materials.json')
    finishes = read(inputs / 'surface_finish.json')
    palette = read(inputs / 'eye_palette.json')
    states = ['neutral', *palette['states']]
    selected = os.environ.get('PBZ_BAIQI_PREVIEW_STATES', 'neutral').split(',')
    assert selected and set(selected) <= set(states)
    names = {compact(name): name for name in materials}
    parents = {masked: preview_parent(inputs, masked) for masked in (False, True)}
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert levels.load_level('/Game/BaiQiBridgeProbe/BridgeAuditMap')
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for command in ('r.Nanite 0', 'r.EyeAdaptationQuality 0', 'r.Tonemapper.GrainQuantization 0'):
        unreal.SystemLibrary.execute_console_command(world, command)
    origin, zero = V(0., 0., 0.), unreal.Rotator()
    camera = actors.spawn_actor_from_class(unreal.SceneCapture2D, origin, zero, transient=True)
    capture = camera.get_component_by_class(unreal.SceneCaptureComponent2D)
    capture.set_editor_property('capture_every_frame', False)
    capture.set_editor_property('capture_on_movement', False)
    capture.set_editor_property('capture_source', unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    capture.set_editor_property('post_process_blend_weight', 0.)
    capture.set_editor_property('fov_angle', 24.)
    target = RENDER.create_render_target2d(world, 640, 640, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    capture.set_editor_property('texture_target', target)
    key = actors.spawn_actor_from_class(unreal.DirectionalLight, origin, unreal.Rotator(pitch=-36., yaw=-54.), transient=True)
    key_light = key.get_component_by_class(unreal.DirectionalLightComponent)
    key_light.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
    key_light.set_editor_property('intensity', 7.)
    fill = actors.spawn_actor_from_class(unreal.DirectionalLight, origin, unreal.Rotator(pitch=-24., yaw=-94.), transient=True)
    fill.get_component_by_class(unreal.DirectionalLightComponent).set_editor_property('intensity', 3.)
    manifest = []
    for form in FORMS:
        model = unreal.load_asset(readback['forms'][form]['mesh'])
        assert isinstance(model, unreal.SkeletalMesh), form
        actor = actors.spawn_actor_from_class(unreal.SkeletalMeshActor, origin, zero, transient=True)
        component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
        component.set_skeletal_mesh_asset(model)
        component.set_cast_shadow(False)
        face = None
        for index, slot in enumerate(model.get_editor_property('materials')):
            name = names[compact(str(slot.get_editor_property('material_slot_name')))]
            spec = materials[name]
            masked = spec['type'] in ('masked', 'hidden')
            instance = component.create_dynamic_material_instance(index, parents[masked])
            assert instance, (form, name)
            apply_maps(inputs, instance, name, spec, finishes.get(name, {}))
            component.set_material(index, instance)
            assert component.get_material(index) == instance
            if name == FACE:
                face = instance
        assert face is not None, form
        head = component.get_socket_location('BaiQi_J_Bip_C_Head') + V(0., 0., 9.)
        for state in selected:
            name = FACE if state == 'neutral' else palette['states'][state]['material']
            apply_maps(inputs, face, name, materials[name], finishes[name])
            for shot, (direction, yaw) in SHOTS.items():
                key.set_actor_rotation(unreal.Rotator(pitch=-36., yaw=yaw), False)
                eye = head + V(*direction) * 101.
                camera.set_actor_location(eye, False, False)
                camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(eye, head), False)
                capture.capture_scene()
                if state == selected[0] and shot == 'front_left':
                    confirm_color(world, target, form)
                file = f'{form}_{state}_{shot}.png'
                RENDER.export_render_target(world, target, str(output), file)
                path = output / file
                assert path.is_file() and path.stat().st_size > 5000, path
                manifest.append({'form': form, 'state': state, 'shot': shot, 'image': file})
        actors.destroy_actor(actor)
    (output / 'preview_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    unreal.log(f'BAIQI_OFFLINE_COLOR_PREVIEW {len(manifest)}')


if __name__ == '__main__':
    main()
