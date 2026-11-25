"""Soften the inward step at the rear of the closed BaiQi skirt."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fit_baiqi_cc0_wardrobe import rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint


SKIRT = 'BaiQi pleated skirt'
ROWS, COLUMNS = 25, 120
MAX_MOVE = .0065


def step_statistics(radius):
    step = np.diff(radius, axis=0)[7:18, 39:82]
    return {'min_radius_step_mm': float(1000 * step.min()),
            'inward_steps_over_2mm': int((step < -.002).sum())}


def smooth_rear_skirt(mesh):
    coordinates = np.array([tuple(vertex.co) for vertex in mesh.vertices]).reshape((ROWS, COLUMNS, 3))
    assert np.allclose(coordinates[..., 2], coordinates[:, 0, 2][:, None])
    centre = np.array([0., .015])
    offset = coordinates[..., :2] - centre
    radius = np.linalg.norm(offset, axis=2)
    assert np.all(radius > .05)
    phase = np.arange(COLUMNS) * math.tau / COLUMNS
    rear = np.clip((-np.cos(phase) - .04) / .36, 0., 1.)
    blended = radius.copy()
    # Soften only the trough left where the earlier hip-fit transitions to
    # the free-hanging panel. The upper attachment and hem stay fixed.
    for _ in range(4):
        for row in range(8, 18):
            average = (blended[row - 1] + 2. * blended[row] + blended[row + 1]) * .25
            blended[row] = np.maximum(blended[row], average)
    step = np.minimum((blended - radius) * rear[None, :], MAX_MOVE)
    points = offset * (1. + step / radius)[..., None] + centre
    changed = np.flatnonzero(step.ravel() > 0.)
    assert 0 < len(changed) < len(mesh.vertices)
    flat = points.reshape(-1, 2)
    for index in changed:
        vertex = mesh.vertices[int(index)]
        vertex.co.x, vertex.co.y = flat[index]
    mesh.update()
    before, after = step_statistics(radius), step_statistics(radius + step)
    assert after['min_radius_step_mm'] > before['min_radius_step_mm']
    return {'changed_vertices': len(changed), 'max_move_mm': float(1000 * step.max()), 'before': before, 'after': after}


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
    forms = {}
    for form in ('coat_on', 'coat_off'):
        base = source / f'BaiQi_CC0_{form}.blend'
        assert fingerprint(base) == manifest[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(base))
        body, head, armature, skirt = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature', SKIRT))
        fixed = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj != skirt}
        assert fixed[body] == manifest[form]['body_sha256']
        rig = rest_signature(armature)
        details = smooth_rear_skirt(skirt.data)
        assert fixed == {obj: mesh_fingerprint(obj) for obj in fixed}
        assert rig == rest_signature(armature)
        target = out / base.name
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        forms[form] = {'candidate_sha256': fingerprint(target), 'cc0_body_sha256': fixed[body],
                       'original_head_sha256': fixed[head], 'drape': details}
    (out / 'skirt_drape.json').write_text(json.dumps(forms, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
