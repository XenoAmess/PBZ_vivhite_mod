"""Replay maintained ROM cases and selected Adult Soul clips on a CC0 fitting."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tools/blender_libs'),
                str(ROOT / 'vendor/UEFormat/plugins/blender')]

from baiqi_cc0_motion import Cc0Motion
from lock_baiqi_cc0_body import mesh_fingerprint
from qa_materials import MaterialReview
from render_baiqi_cc0_fitting import setup_studio


NATIVE_CLIPS = ('Hun_Unarmed_Idle_Loop', 'Hun_Unarmed_Run_Fwd_Loop', 'Hun_BaiShanDual_Attack_A')
NECK_ZONES = {'neck': (.0, .052, 1.320, 1.369)}
ARM_ZONES = {'shoulder': (.125, .238, 1.190, 1.325), 'elbow': (.292, .363, 1.196, 1.319)}
VIEWS = {'front': (0, 1, 0), 'back': (0, -1, 0), 'side': (-1, 0, 0), 'oblique': (-.57, .82, 0)}


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def set_action(armature, action):
    data = armature.animation_data_create()
    data.action = action
    if action.slots:
        data.action_slot = action.slots[0]


def load_source(path, names):
    with bpy.data.libraries.load(str(path), link=False) as (available, assets):
        assert set(names).issubset(available.actions), [name for name in names if name not in available.actions]
        assets.actions = list(names)
        assets.objects = ['Armature']
    soul = assets.objects[0]
    bpy.context.scene.collection.objects.link(soul)
    soul.name = 'Adult Soul motion source'
    return soul, dict(zip(names, assets.actions))


def evaluated_points(obj, graph):
    return np.array([tuple(vertex.co) for vertex in obj.evaluated_get(graph).data.vertices])


class Stretch:
    def __init__(self, obj, zones):
        self.obj = obj
        graph = bpy.context.evaluated_depsgraph_get()
        mesh = obj.evaluated_get(graph).data
        positions = evaluated_points(obj, graph)
        edges = np.array([tuple(edge.vertices) for edge in mesh.edges])
        lengths = np.linalg.norm(positions[edges[:, 0]] - positions[edges[:, 1]], axis=1)
        self.regions = {}
        x, _, z = positions.T
        for name, (xmin, xmax, zmin, zmax) in zones.items():
            allowed = (abs(x) >= xmin) & (abs(x) < xmax) & (z > zmin) & (z < zmax)
            valid = allowed[edges[:, 0]] & allowed[edges[:, 1]] & (lengths > .00045)
            assert valid.any(), (obj.name, name)
            self.regions[name] = edges[valid], lengths[valid]

    def sample(self, graph):
        vertices = evaluated_points(self.obj, graph)
        assert np.isfinite(vertices).all(), self.obj.name
        result = {}
        for region, (edges, rest) in self.regions.items():
            ratios = np.linalg.norm(vertices[edges[:, 0]] - vertices[edges[:, 1]], axis=1) / rest
            result[region] = {'stretch_p95': float(np.percentile(ratios, 95)), 'stretch_max': float(ratios.max()),
                              'compression_p05': float(np.percentile(ratios, 5))}
        return result


def surface_tree(obj, graph, skin=False):
    mesh = obj.evaluated_get(graph).data
    coords = [v.co for v in mesh.vertices]
    mesh.calc_loop_triangles()
    triangles = [tuple(triangle.vertices) for triangle in mesh.loop_triangles
                 if not skin or max(coords[i].z for i in triangle.vertices) < 1.305]
    return BVHTree.FromPolygons(coords, triangles, all_triangles=True)


def render_kind(studio, camera, scene, row, target, out, kind, views, label, size):
    studio(kind)
    camera.data.ortho_scale = size
    for view in views:
        camera.location = target + Vector(VIEWS[view]) * 3
        camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
        relative = Path('samples') / row['id'] / kind / f'{label}_{view}.png'
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        row['images'].append(relative.as_posix())


def prepare_studio(meshes, body):
    review = MaterialReview(meshes)
    body_mask = next(node for modifier in body.modifiers if modifier.type == 'NODES'
                     for node in modifier.node_group.nodes if node.type == 'SET_MATERIAL')
    mask_slot = body_mask.inputs['Material']
    actual = mask_slot.default_value
    gray = actual.copy()
    for material in [gray, *review.clay.values()]:
        for node in material.node_tree.nodes:
            if node.type == 'EMISSION':
                for link in list(node.inputs['Color'].links):
                    material.node_tree.links.remove(link)
                node.inputs['Color'].default_value = (.38, .42, .45, 1)

    def apply(kind):
        review.apply(kind)
        mask_slot.default_value = gray if kind == 'clay' else actual

    return apply


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--donor', required=True, type=Path)
    parser.add_argument('--suite', default=Path('qa/suites/humanoid_v1_1.json'), type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--render', choices=('full', 'triage', 'none'), default='full')
    parser.add_argument('--case', action='append', default=[], help='Limit the run to named cases or native clips.')
    parser.add_argument('--forearm-roll-share', type=float, default=1.)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = ROOT / args.out
    output.mkdir(parents=True, exist_ok=True)
    photo = ROOT / args.candidate
    donor = ROOT / args.donor
    suite_path = ROOT / args.suite
    spec = json.loads(suite_path.read_text(encoding='utf-8'))
    donor_report = json.loads((donor.parent / 'sampling_report.json').read_text(encoding='utf-8'))
    assert donor_report['input_hashes']['suite'] == file_hash(suite_path)
    declared = [(case['id'], [sample['value'] for sample in case['samples']]) for case in spec['cases']]
    donor_cases = [(clip['id'], [sample['value'] for sample in clip['samples']]) for clip in donor_report['clips']]
    assert donor_cases == declared, 'Motion donor does not match the maintained sample grid.'
    assert set(args.case).issubset({case['id'] for case in spec['cases']} | set(NATIVE_CLIPS)), args.case
    bpy.ops.wm.open_mainfile(filepath=str(photo))
    scene = bpy.context.scene
    body = bpy.data.objects['Body']
    cc0 = bpy.data.objects['Armature']
    assert mesh_fingerprint(body) == body['baiqi_cc0_geometry_sha256']
    head = bpy.data.objects['BaiQi restored authored head and face']
    meshes = [obj for obj in scene.objects if obj.type == 'MESH' and not obj.hide_render]
    for obj in meshes:
        binding = [modifier for modifier in obj.modifiers if modifier.type == 'ARMATURE']
        assert len(binding) == 1 and binding[0].object == cc0 and not binding[0].use_deform_preserve_volume, obj.name
    wardrobe = [obj for obj in meshes if obj.name.startswith(('BaiQi fitted sleeveless',
                                                               'BaiQi fitted navy', 'BaiQi pleated',
                                                               'BaiQi open coat'))]
    checks = [Stretch(body, ARM_ZONES), Stretch(head, NECK_ZONES)]
    soul, actions = load_source(donor, [row['action'] for row in donor_report['clips']])
    assert 0 <= args.forearm_roll_share <= 1
    transfer = Cc0Motion(soul, cc0, args.forearm_roll_share)
    camera = setup_studio(scene)
    lights = {obj.name: obj.location.copy() for obj in scene.objects if obj.type == 'LIGHT'}
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.eevee.taa_render_samples = 24
    studio = prepare_studio(meshes, body)
    rows = []

    def assess(case_id, group, action, samples, source_hash=None):
        set_action(soul, action)
        row = {'id': case_id, 'group': group, 'samples': [], 'images': [], 'source_sha256': source_hash}
        rows.append(row)
        for index, sample in enumerate(samples):
            scene.frame_set(sample['frame'])
            bpy.context.view_layer.update()
            transfer.apply()
            bpy.context.view_layer.update()
            graph = bpy.context.evaluated_depsgraph_get()
            metrics = {}
            for check in checks:
                metrics.update(check.sample(graph))
            skin = surface_tree(body, graph, skin=True)
            intersections = {obj.name: len(skin.overlap(surface_tree(obj, graph))) for obj in wardrobe}
            alignment = max(math.degrees(error) for error in transfer.angle_errors().values())
            row['samples'].append({**sample, 'metrics': metrics, 'max_mapped_segment_error_degrees': alignment,
                                   'intersecting_skin_apparel_triangle_pairs': intersections})
            if args.render == 'none' or (args.render == 'triage' and index not in {0, len(samples) // 2, len(samples) - 1}):
                continue
            camera_height, size = {'neck': (1.39, .57), 'arms': (1.13, 1.60), 'body': (.82, 1.95)}[group]
            root = cc0.pose.bones['Root'].head
            target = root + Vector((0, 0, camera_height))
            for name, studio_location in lights.items():
                scene.objects[name].location = studio_location + root
            for kind in spec['passes']:
                render_kind(studio, camera, scene, row, target, output, kind,
                            spec['views'][group], f'{index:02}', size)
            studio('textured')
        print('BAIQI_CC0_CASE', case_id, len(row['samples']), len(row['images']), flush=True)

    for clip in donor_report['clips']:
        if args.case and clip['id'] not in args.case:
            continue
        samples = [{key: sample[key] for key in ('frame', 'value', 'label')} for sample in clip['samples']]
        assess(clip['id'], clip['group'], actions[clip['action']], samples)

    from io_scene_ueformat.importer.import_context import UEFormatImport
    from io_scene_ueformat.options import UEAnimOptions

    for name in NATIVE_CLIPS:
        if args.case and name not in args.case:
            continue
        path = ROOT / 'repro/game_reference/animations' / (name + '.ueanim')
        UEFormatImport(UEAnimOptions(scale_factor=1., override_skeleton=soul, import_curves=False)).import_file(path)
        action = soul.animation_data.action
        assert action is not None, name
        start, stop = (float(frame) for frame in action.frame_range)
        samples = [{'frame': round(start + (stop - start) * fraction), 'value': fraction}
                   for fraction in (0., .25, .5, .75, 1.)]
        assess(name, 'body', action, samples, file_hash(path))

    flags = []
    for row in rows:
        for sample in row['samples']:
            for region, metrics in sample['metrics'].items():
                for key, limit in spec['thresholds'][region].items():
                    if metrics[key] > limit:
                        flags.append({'case': row['id'], 'frame': sample['frame'], 'region': region,
                                      'metric': key, 'value': metrics[key], 'limit': limit})
    coverage = not args.case and args.render == 'full' and all(len(row['images']) == len(row['samples']) * 6 for row in rows)
    studio('textured')
    assert mesh_fingerprint(body) == body['baiqi_cc0_geometry_sha256']
    report = {'status': 'failed' if flags else 'pending_review', 'game_runtime_allowed': False,
              'model_sha256': file_hash(photo), 'suite_sha256': file_hash(suite_path), 'suite_version': spec['version'],
              'donor_sha256': file_hash(donor), 'runner_sha256': file_hash(Path(__file__)),
              'retarget_sha256': file_hash(Path(__file__).with_name('baiqi_cc0_motion.py')),
              'mapped_bones': len(transfer.links), 'render_profile': args.render,
              'forearm_roll_share': args.forearm_roll_share,
              'full_render_coverage': coverage, 'flags': flags, 'clips': rows,
              'limits': ['Adult Soul motion samples exclude runtime AnimBP, IK and physics.',
                         'Apparel intersection counts require visual review and include intentional overlap.']}
    (output / 'motion_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
