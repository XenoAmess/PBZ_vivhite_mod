"""Render identical face and neckline angles under matched directional lights."""
import argparse
from pathlib import Path
import sys

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from render_baiqi_cc0_fitting import pose_arms, setup_studio
from run_baiqi_cc0_motion_review import match_game_hair_shadows


LIGHTS = {'left': (-1.12, 1.08, 1.82), 'right': (1.12, 1.08, 1.82), 'rim': (.25, -1.4, 1.86)}
FACE = 'BaiQi original face appearance'


def render_form(path, out, version, form):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene = bpy.context.scene
    camera = setup_studio(scene)
    pose_arms(bpy.data.objects['Armature'], -56, 0)
    meshes = [obj for obj in scene.objects if obj.type == 'MESH' and not obj.hide_render]
    match_game_hair_shadows(scene, meshes)
    key, fill, rim = [obj for obj in scene.objects if obj.type == 'LIGHT'][:3]
    key.data.energy, key.data.size = 136, .50
    fill.location = Vector((0., 1.7, 1.75))
    fill.data.energy, fill.data.size = 33, 1.55
    rim.data.energy = 13
    face = Vector((0, -.011, 1.470))
    neckline = Vector((0, -.003, 1.375))
    fill.rotation_euler = (face - fill.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.resolution_x = scene.render.resolution_y = 640
    scene.eevee.taa_render_samples = 48

    def render(label, target, direction, size, light):
        key.location = Vector(LIGHTS[light])
        key.rotation_euler = (face - key.location).to_track_quat('-Z', 'Y').to_euler()
        camera.location = target + 3 * Vector(direction)
        camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
        camera.data.ortho_scale = size
        scene.render.filepath = str(out / f'{version}_{form}_{label}.png')
        bpy.ops.render.render(write_still=True)

    for lamp in ('left', 'right', 'rim'):
        render(lamp, face, (-.36, .932, 0), .315, lamp)
    render('collar', neckline, (-.28, .96, 0), .54, 'right')
    if form == 'coat_off':
        for obj in meshes:
            if obj.name.startswith(('BaiQi round gold glasses', 'BaiQi glasses temple')):
                obj.hide_render = True
        for lamp in ('left', 'right'):
            render('front_' + lamp, face, (0, 1, 0), .31, lamp)
        normal = next((node for node in bpy.data.materials[FACE].node_tree.nodes
                       if node.label == 'Local skin relief response'), None)
        if normal:
            normal.inputs['Strength'].default_value = 0.
            for lamp in ('left', 'right'):
                render('flat_normal_' + lamp, face, (0, 1, 0), .31, lamp)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    for version, source in [('control', args.control), ('candidate', args.candidate)]:
        for form in ('coat_on', 'coat_off'):
            render_form(ROOT / source / f'BaiQi_CC0_{form}.blend', out, version, form)


if __name__ == '__main__':
    main()
