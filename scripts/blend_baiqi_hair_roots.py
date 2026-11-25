"""Tuck the repeated bob roots under a continuous crown on both forms."""
import argparse
import json
from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from finish_baiqi_surfaces import FRINGE, window
from fit_baiqi_cc0_wardrobe import rest_signature, smoothstep
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint
from refine_baiqi_hair_finish import CLUMP_PREFIX, edit_mesh


CROWN = 'BaiQi crown under hair'
CENTRE_X, CENTRE_Y = .000255, -.031


def rescale_crown_sections(mesh, strength):
    for vertex in mesh.vertices:
        p = vertex.co
        back = smoothstep((.035 - p.y) / .041)
        fill = strength * .085 * back * window(p.z, 1.566, 1.604, 1.6315)
        p.x += (p.x - CENTRE_X) * fill
        p.y += (p.y - CENTRE_Y) * fill
        front = smoothstep((p.y - .009) / .025)
        centre = 1. - smoothstep(abs(p.x - CENTRE_X) / .056)
        # Tuck a wider cap under the two open sections between fringe panels.
        p.y += .018 * front * centre * window(p.z, 1.574, 1.605, 1.632)
    mesh.update()


def tuck_rear_roots(mesh, strength):
    for vertex in mesh.vertices:
        p = vertex.co
        tuck = strength * .154 * window(p.z, 1.565, 1.600, 1.629)
        p.x += (CENTRE_X - p.x) * tuck
        p.y += (CENTRE_Y - p.y) * tuck
    mesh.update()


def lower_fringe_peaks(mesh, strength):
    for vertex in mesh.vertices:
        p = vertex.co
        top = smoothstep((p.z - 1.614) / .017)
        off_centre = smoothstep(abs(p.x - CENTRE_X) / .036)
        p.z -= .0045 * strength * top * off_centre
    mesh.update()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default=ROOT / 'output/live2d_delta/baiqi_058_tailoring', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--strength', default=1., type=float)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, output = args.source.resolve(), args.out.resolve()
    assert source != output and output.is_relative_to(ROOT)
    assert .3 <= args.strength <= 1.5
    expected = json.loads((source / 'tailoring.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    report = {}
    for form in ('coat_on', 'coat_off'):
        path = source / f'BaiQi_CC0_{form}.blend'
        record = expected[form]
        source_hash = fingerprint(path)
        assert source_hash == record['candidate_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        scene = bpy.context.scene
        objects = bpy.data.objects
        crown, fringe = objects[CROWN], objects[FRINGE]
        clumps = [obj for obj in scene.objects if obj.name.startswith(CLUMP_PREFIX)]
        assert len(clumps) == 23
        touched = {crown, fringe, *clumps}
        protected = {obj: mesh_fingerprint(obj) for obj in scene.objects if obj.type == 'MESH' and obj not in touched}
        assert protected[objects['Body']] == record['cc0_body_sha256']
        assert protected[objects[HEAD]] == record['original_head_sha256']
        rig = rest_signature(objects['Armature'])
        changes = {obj.name: edit_mesh(obj, lambda mesh: tuck_rear_roots(mesh, args.strength)) for obj in clumps}
        changes[crown.name] = edit_mesh(crown, lambda mesh: rescale_crown_sections(mesh, args.strength))
        changes[fringe.name] = edit_mesh(fringe, lambda mesh: lower_fringe_peaks(mesh, args.strength))
        assert all(mesh_fingerprint(obj) == value for obj, value in protected.items())
        assert rest_signature(objects['Armature']) == rig
        destination = output / path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(destination))
        report[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(destination),
                        'cc0_body_sha256': record['cc0_body_sha256'], 'original_head_sha256': record['original_head_sha256'],
                        'strength': args.strength, 'moves': changes}
    (output / 'hair_root_blend.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
