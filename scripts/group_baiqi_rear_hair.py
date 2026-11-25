"""Shape the lower rear locks into groups while retaining the crown and nape cover."""
import argparse
import json
from pathlib import Path
import sys

import bpy
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fit_baiqi_cc0_wardrobe import rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint
from refine_baiqi_hair_finish import CLUMP_PREFIX, ROW_COUNT, ROW_WIDTH


GROUPS = ((2, 3, 4), (5, 6), (7, 8, 9), (10, 11, 12), (13, 14, 15), (16, 17), (18, 19, 20))
TIP_OFFSET_MM = (1.8, -3., 2.4, 3., -3.5, 1., -3.6, 2.5, 3.3, -2.5,
                 2.2, -1., -3.2, 2.7, -3.8, 2.5, 2.4, -2.6, 1.7)
CENTER = np.array((.000255, -.031))
STRENGTH = .68


def smooth(weight):
    weight = np.clip(weight, 0., 1.)
    return weight**2 * (3. - 2. * weight)


def shape_group(locks, group, lengths, angles):
    centre = sum(group) / len(group)
    report = {}
    for index in group:
        obj = locks[index]
        vertices = obj.data.vertices
        assert len(vertices) == ROW_COUNT * ROW_WIDTH
        old = np.array([vertex.co[:] for vertex in vertices]).reshape(ROW_COUNT, ROW_WIDTH, 3)
        new = old.copy()
        tangent = (centre - index) * .037 * angles
        cosine, sine = np.cos(tangent)[:, None], np.sin(tangent)[:, None]
        xy = old[..., :2] - CENTER
        midpoint = ROW_WIDTH // 2
        across = xy - xy[:, midpoint:midpoint + 1, :]
        # Keep the group edges wide enough to cover the gaps near the nape.
        width = (.19 if index == group[len(group) // 2] else .27) * lengths
        spread = xy + across * width[:, None, None]
        new[..., 0] = CENTER[0] + cosine * spread[..., 0] - sine * spread[..., 1]
        new[..., 1] = CENTER[1] + sine * spread[..., 0] + cosine * spread[..., 1]
        new[..., 2] += TIP_OFFSET_MM[index - 2] * .001 * lengths[:, None]
        positions = new.reshape(-1, 3)
        changed = 0
        for vertex, position in zip(vertices, positions, strict=True):
            if lengths[vertex.index // ROW_WIDTH] > 0.:
                vertex.co = position
                changed += 1
        obj.data.update()
        maximum = float(np.linalg.norm(new - old, axis=2).max() * 1000.)
        assert 0 < maximum < 4.1
        report[obj.name] = {'moved_vertices': changed, 'max_move_mm': maximum}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, out = ((ROOT / path).resolve() for path in (args.source, args.source_inputs, args.out))
    assert source != out and out.is_relative_to(ROOT)
    manifest = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    out.mkdir(parents=True, exist_ok=True)
    travel = np.linspace(0., 1., ROW_COUNT)
    lengths = smooth((travel - .47) / .53) * STRENGTH
    angles = smooth((travel - .63) / .37) * STRENGTH
    forms = {}
    for form in ('coat_on', 'coat_off'):
        base = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(base)
        assert source_hash == manifest[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(base))
        objects = bpy.data.objects
        locks = [objects[f'{CLUMP_PREFIX}{index}'] for index in range(23)]
        edited = {locks[index] for group in GROUPS for index in group}
        locked = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj not in edited}
        assert locked[objects['Body']] == manifest[form]['body_sha256']
        rig = rest_signature(objects['Armature'])
        changes = {}
        for group in GROUPS:
            changes.update(shape_group(locks, group, lengths, angles))
        assert locked == {obj: mesh_fingerprint(obj) for obj in locked}
        assert rig == rest_signature(objects['Armature'])
        target = out / base.name
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        forms[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(target),
                       'cc0_body_sha256': locked[objects['Body']], 'original_head_sha256': locked[objects[HEAD]],
                       'groups': GROUPS, 'changed_locks': changes}
    (out / 'rear_hair_groups.json').write_text(json.dumps(forms, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
