"""Soften the restored bob clumps and curve the headdress around the head."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fit_baiqi_cc0_wardrobe import rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint


CLUMP_PREFIX = 'BaiQi rear hair clump '
HEADDRESS = 'BaiQi black gold headdress'
ROW_COUNT = 48
ROW_WIDTH = 9


def soften_clump(mesh):
    assert len(mesh.vertices) == ROW_COUNT * ROW_WIDTH, mesh.name
    for row in range(ROW_COUNT):
        start = row * ROW_WIDTH
        length = row / (ROW_COUNT - 1)
        # Taper the correction at the crown and tips, where the original
        # sheets overlap less and define the silhouette.
        root_fade = math.sin(min(1., max(0., length - .10) / .19) * math.pi / 2)
        tip_fade = 1 - .7 * max(0., length - .73) / .27
        first, last = mesh.vertices[start].co.copy(), mesh.vertices[start + ROW_WIDTH - 1].co.copy()
        for column in range(1, ROW_WIDTH - 1):
            vertex = mesh.vertices[start + column]
            chord = first.lerp(last, column / (ROW_WIDTH - 1))
            vertex.co = vertex.co.lerp(chord, .50 * root_fade * tip_fade)
    mesh.update()


def curve_headdress(mesh):
    for vertex in mesh.vertices:
        x = vertex.co.x - .000255
        distance = min(1., max(0., (abs(x) - .108) / .083))
        taper = distance ** 2 * (3 - 2 * distance)
        vertex.co.y -= .022 * taper
        vertex.co.x += math.copysign(.0015 * distance, x)
    mesh.update()


def edit_mesh(obj, edit):
    before = [vertex.co.copy() for vertex in obj.data.vertices]
    previous = mesh_fingerprint(obj)
    edit(obj.data)
    result = [vertex.co.copy() for vertex in obj.data.vertices]
    displacement = max((a - b).length for a, b in zip(before, result, strict=True))
    assert displacement > 0, obj.name
    for vertex, position in zip(obj.data.vertices, before, strict=True):
        vertex.co = position
    assert mesh_fingerprint(obj) == previous, obj.name
    for vertex, position in zip(obj.data.vertices, result, strict=True):
        vertex.co = position
    obj.data.update()
    return {'vertices': len(result), 'sha256': mesh_fingerprint(obj), 'max_shift_mm': displacement * 1000}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'output/live2d_delta/baiqi_055_face_finish')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, output = args.source.resolve(), args.out.resolve()
    assert source != output and output.is_relative_to(ROOT)
    pinned = json.loads((source / 'face_lighting.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    report = {}
    for form in ('coat_on', 'coat_off'):
        path = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(path)
        assert pinned[form]['candidate_sha256'] == source_hash
        bpy.ops.wm.open_mainfile(filepath=str(path))
        objects = bpy.data.objects
        body, head, rig = objects['Body'], objects[HEAD], objects['Armature']
        hair = sorted((obj for obj in bpy.context.scene.objects if obj.name.startswith(CLUMP_PREFIX)),
                      key=lambda obj: obj.name)
        assert len(hair) == 23 and all(not obj.hide_render for obj in hair)
        headdress = objects[HEADDRESS]
        edited = {*hair, headdress}
        before = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects
                  if obj.type == 'MESH' and obj not in edited}
        assert before[body] == pinned[form]['cc0_body_sha256'] == body['baiqi_cc0_geometry_sha256']
        assert before[head] == pinned[form]['authored_head_mesh_sha256']
        skeleton = rest_signature(rig)
        changes = {obj.name: edit_mesh(obj, soften_clump) for obj in hair}
        changes[headdress.name] = edit_mesh(headdress, curve_headdress)
        assert all(mesh_fingerprint(obj) == digest for obj, digest in before.items())
        assert rest_signature(rig) == skeleton
        destination = output / path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(destination))
        report[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(destination),
                        'cc0_body_sha256': before[body], 'original_head_sha256': before[head], 'edited': changes}
    (output / 'hair_finish.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('BAIQI_HAIR_CANDIDATE', output, flush=True)


if __name__ == '__main__':
    main()
