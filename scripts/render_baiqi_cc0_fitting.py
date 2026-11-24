"""Render the two wardrobe forms on the same CC0 rig for offline fit review."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion, Vector


ROOT = Path(__file__).resolve().parents[1]
VIEWS = {
    'front': (0, 1, 0),
    'oblique': (-.58, .81, 0),
    'side': (-1, 0, 0),
    'back': (0, -1, 0),
}
POSES = {
    'relaxed': (-56, 0), 'arms_out': (-17, 0), 'reach_forward': (-28, 50),
    'head_turn': (-56, 0), 'head_turn_opposite': (-56, 0), 'look_up': (-56, 0),
    'look_down': (-56, 0), 'head_tilt': (-56, 0),
}


def setup_studio(scene):
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 24
    scene.render.resolution_x = scene.render.resolution_y = 760
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.exposure = -.25
    for location, watts, size in [((-.8, 1.6, 2.3), 115, 1.6), ((.8, 1.15, 1.4), 54, 1.6),
                                  ((.25, -1.3, 2.1), 120, 1.6)]:
        light = bpy.data.lights.new('Fitting softbox', 'AREA')
        light.energy = watts
        light.size = size
        obj = bpy.data.objects.new(light.name, light)
        scene.collection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (Vector((0, 0, 1.12)) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    optics = bpy.data.cameras.new('Fitting camera')
    optics.type = 'ORTHO'
    optics.clip_start = .01
    optics.clip_end = 15
    camera = bpy.data.objects.new(optics.name, optics)
    scene.collection.objects.link(camera)
    scene.camera = camera
    return camera


def pose_arms(rig, elevation, forward):
    for side, sign in [('L', -1), ('R', 1)]:
        upper = rig.pose.bones[f'J_Bip_{side}_UpperArm']
        lower = rig.pose.bones[f'J_Bip_{side}_LowerArm']
        upper_rest = upper.bone.matrix_local.to_quaternion()
        lower_rest = lower.bone.matrix_local.to_quaternion()
        swing = Quaternion((0, 0, 1), math.radians(forward * sign))
        drop = Quaternion((0, 1, 0), math.radians(-elevation * sign))
        bend = Quaternion((0, 0, 1), math.radians(6 * sign))
        upper.rotation_mode = lower.rotation_mode = 'QUATERNION'
        upper.rotation_quaternion = upper_rest.inverted() @ swing @ drop @ upper_rest
        lower.rotation_quaternion = lower_rest.inverted() @ bend @ lower_rest
    bpy.context.view_layer.update()


def pose_head(rig, pose):
    head = rig.pose.bones['J_Bip_C_Head']
    neck = rig.pose.bones['J_Bip_C_Neck']
    axis, angle = {
        'head_turn': ((0, 0, 1), 41),
        'head_turn_opposite': ((0, 0, 1), -41),
        'look_up': ((1, 0, 0), 25),
        'look_down': ((1, 0, 0), -27),
        'head_tilt': ((0, 1, 0), 18),
    }.get(pose, ((0, 0, 1), 0))
    for bone, fraction in [(neck, .25), (head, .75)]:
        rest = bone.bone.matrix_local.to_quaternion()
        bone.rotation_mode = 'QUATERNION'
        bone.rotation_quaternion = rest.inverted() @ Quaternion(axis, math.radians(angle * fraction)) @ rest
    bpy.context.view_layer.update()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fitting', required=True, type=Path)
    parser.add_argument('--form', choices=('coat_on', 'coat_off'), required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    fitting = ROOT / args.fitting
    output = fitting / 'review'
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(fitting / f'BaiQi_CC0_{args.form}.blend'))
    scene = bpy.context.scene
    camera = setup_studio(scene)
    rig = bpy.data.objects['Armature']
    samples = [('relaxed', name, False) for name in VIEWS]
    samples.extend((pose, view, True) for pose, view in [('relaxed', 'front'), ('relaxed', 'side'),
                                                        ('arms_out', 'front'), ('reach_forward', 'oblique'),
                                                        ('head_turn', 'front'), ('look_up', 'side'),
                                                        ('head_turn_opposite', 'front'), ('look_down', 'side'),
                                                        ('head_tilt', 'oblique')])
    report = []
    for pose, view, torso in samples:
        pose_arms(rig, *POSES[pose])
        pose_head(rig, pose)
        target = Vector((0, 0, 1.235 if torso else .806))
        camera.data.ortho_scale = .86 if torso else 1.76
        camera.location = target + Vector(VIEWS[view]) * 3
        camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
        name = f'{args.form}_{pose}_{view}' + ('_torso' if torso else '') + '.png'
        scene.render.filepath = str(output / name)
        bpy.ops.render.render(write_still=True)
        report.append({'image': name, 'pose': pose, 'view': view, 'torso': torso})
    (output / f'{args.form}_review.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
