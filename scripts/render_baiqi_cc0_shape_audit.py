"""Render the maintained 13-section static review on the CC0 wardrobe forms."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from render_baiqi_cc0_fitting import pose_arms, setup_studio
from run_baiqi_cc0_motion_review import file_hash, prepare_studio


def section_targets(armature):
    p = {bone.name: bone.head.copy() for bone in armature.pose.bones}
    targets = {
        'head': ((0, .02, 1.475), .47), 'neck_shoulders': ((0, .02, 1.318), .61),
        'torso': ((0, .02, 1.128), .76), 'pelvis': ((0, .01, .920), .64),
        'legs': ((0, 0, .453), 1.02), 'knees': ((0, .02, .447), .45), 'feet': ((0, .025, .105), .36),
    }
    for side, tag in [('L', 'left'), ('R', 'right')]:
        shoulders = p[f'J_Bip_{side}_UpperArm']
        elbow = p[f'J_Bip_{side}_LowerArm']
        wrist = p[f'J_Bip_{side}_Hand']
        hand = p[f'J_Bip_{side}_Middle2']
        targets['upper_arm_' + tag] = (shoulders.lerp(elbow, .5), .42)
        targets['elbow_' + tag] = (elbow, .32)
        targets['hand_' + tag] = (wrist.lerp(hand, .55), .27)
    return targets


def review_form(candidate, out, spec, config):
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(candidate))
    scene = bpy.context.scene
    camera = setup_studio(scene)
    scene.render.resolution_x = scene.render.resolution_y = 600
    arm = bpy.data.objects['Armature']
    body = bpy.data.objects['Body']
    studio = prepare_studio([obj for obj in scene.objects if obj.type == 'MESH' and not obj.hide_render], body)
    pose_arms(arm, -56, 0)
    targets = section_targets(arm)
    sections = [section['id'] for section in spec['sections']]
    assert set(sections) == set(targets)
    targets['full_body'] = ((0, 0, .808), 1.763)
    records = []
    for kind in spec['passes']:
        studio(kind)
        for name in ['full_body', *sections]:
            point, span = targets[name]
            target = Vector(point)
            camera.data.ortho_scale = span
            angles = spec['full_body']['angles_deg'] if name == 'full_body' else spec['detail_views_deg']
            for angle in angles:
                theta = math.radians(angle)
                camera.location = target + Vector((-math.sin(theta), math.cos(theta), 0)) * 3
                camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
                relative = Path(name) / kind / f'{angle:03}.png'
                frame = out / relative
                frame.parent.mkdir(parents=True, exist_ok=True)
                scene.render.filepath = str(frame)
                bpy.ops.render.render(write_still=True)
                records.append({'section': name, 'pass': kind, 'angle_deg': angle, 'path': relative.as_posix()})
    expected = len(spec['passes']) * (len(spec['full_body']['angles_deg']) + len(sections) * len(spec['detail_views_deg']))
    assert len(records) == expected
    report = {'shape_suite_version': spec['version'], 'sections': sections, 'images': records, 'expected_images': expected,
              'coverage_complete': True, 'input_hashes': {'model': file_hash(candidate), 'suite': file_hash(config)},
              'status': 'pending_visual_review', 'game_runtime_allowed': False}
    (out / 'shape_manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    config = ROOT / 'qa/shape_audit_v1.json'
    spec = json.loads(config.read_text(encoding='utf-8'))
    for form in ('coat_off', 'coat_on'):
        review_form(ROOT / args.candidate / f'BaiQi_CC0_{form}.blend', ROOT / args.out / form, spec, config)


if __name__ == '__main__':
    main()
