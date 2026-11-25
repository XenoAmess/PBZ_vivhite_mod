"""Give the two local coat underarm folds clearance over the fitted blouse."""
import argparse
import json
import math
from pathlib import Path
from shutil import copyfile
import sys

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from finish_baiqi_surfaces import COAT
from fit_baiqi_cc0_wardrobe import rest_signature, smoothstep
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint


def free_underarm_cloth(mesh):
    distances = []
    for vertex in mesh.vertices:
        point = vertex.co
        radius = math.sqrt(((abs(point.x) - .125) / .041) ** 2
                           + ((point.y - .048) / .029) ** 2 + ((point.z - 1.221) / .042) ** 2)
        if radius >= 1.:
            continue
        weight = smoothstep(min(1., (1. - radius) / .60))
        outward = Vector((math.copysign(.82, point.x), math.sqrt(1. - .82 ** 2), 0.))
        offset = outward * (.0046 * weight)
        vertex.co += offset
        distances.append(offset.length)
    mesh.update()
    assert distances and max(distances) <= .00461
    return {'vertices': len(distances), 'max_delta_mm': 1000 * max(distances)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, out = ((ROOT / path).resolve() for path in (args.source, args.source_inputs, args.out))
    assert source != out and out.is_relative_to(ROOT)
    expected = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    for form in ('coat_on', 'coat_off'):
        path = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(path)
        assert source_hash == expected[form]['source_sha256']
        target = out / path.name
        if form == 'coat_off':
            copyfile(path, target)
            assert fingerprint(target) == source_hash
            report[form] = {'source_sha256': source_hash, 'candidate_sha256': source_hash, 'vertices': 0}
            continue
        bpy.ops.wm.open_mainfile(filepath=str(path))
        body, head, rig, coat = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature', COAT))
        fixed = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj != coat}
        skeleton = rest_signature(rig)
        assert fixed[body] == expected[form]['body_sha256']
        changes = free_underarm_cloth(coat.data)
        assert all(mesh_fingerprint(obj) == value for obj, value in fixed.items())
        assert rest_signature(rig) == skeleton
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        report[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(target),
                        'cc0_body_sha256': fixed[body], 'authored_head_sha256': fixed[head], **changes}
    (out / 'coat_underarms.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(report, flush=True)


if __name__ == '__main__':
    main()
