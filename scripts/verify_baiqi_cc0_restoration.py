"""Verify the preserved CC0 body and restored BaiQi face against their sources."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fit_baiqi_cc0_wardrobe import head_position, rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint


FACE_MATERIAL = 'BaiQi original face appearance'


def face_geometry(mesh, map_coordinate):
    slot = mesh.materials.find(FACE_MATERIAL)
    assert slot >= 0
    mesh.calc_loop_triangles()
    uv = mesh.uv_layers['BaiQiCanvas'].uv
    geometry = []
    for triangle in mesh.loop_triangles:
        if triangle.material_index != slot:
            continue
        corners = [
            (*map_coordinate(mesh.vertices[vertex].co), *uv[loop].vector)
            for vertex, loop in zip(triangle.vertices, triangle.loops)
        ]
        geometry.append(sorted(corners))
    return np.array(geometry)


def face_art_sha256(mesh):
    material = mesh.materials[FACE_MATERIAL]
    image = next(node.image for node in material.node_tree.nodes if node.type == 'TEX_IMAGE')
    return hashlib.sha256(image.packed_file.data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, default=Path('artifacts/anatomy_base/Base_Female.blend'))
    parser.add_argument('--head-from', type=Path, required=True)
    parser.add_argument('--fitting', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = ROOT / args.fitting
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / args.base))
    names = ('Body', 'Face')
    fingerprints = {name: mesh_fingerprint(bpy.data.objects[name]) for name in names}
    skeleton = rest_signature(bpy.data.objects['Armature'])
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / args.head_from))
    source = bpy.data.objects['BaiQi_FemaleFoundation'].data
    legacy = face_geometry(source, head_position)
    atlas = face_art_sha256(source)
    assert legacy.size > 0

    checks = {}
    for form in ('coat_off', 'coat_on'):
        path = output / f'BaiQi_CC0_{form}.blend'
        bpy.ops.wm.open_mainfile(filepath=str(path))
        objects = bpy.data.objects
        assert {name: mesh_fingerprint(objects[name]) for name in names} == fingerprints
        assert rest_signature(objects['Armature']) == skeleton
        assert [obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE'] == [objects['Armature']]
        assert objects['Face'].hide_render and objects['Face'].hide_get()
        head = objects['BaiQi restored authored head and face']
        assert not head.hide_render and not head.hide_get()
        assert all(obj.hide_render == (form == 'coat_off')
                   for obj in bpy.data.collections['BaiQi coat and sleeve accessories'].objects)
        geometry = face_geometry(head.data, lambda point: point)
        assert geometry.shape == legacy.shape, (form, geometry.shape, legacy.shape)
        error = np.abs(geometry - legacy).max(axis=(0, 1))
        assert error.max() < 2e-6, (form, error)
        assert face_art_sha256(head.data) == atlas
        assert all(image.source != 'FILE' or image.packed_file for image in bpy.data.images)
        checks[form] = {
            'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'original_body_fingerprints_match': True,
            'restored_face_triangles': len(geometry),
            'max_restored_face_position_and_uv_error': error.tolist(),
            'restored_face_atlas_matches': True,
        }
    (output / 'restoration_verification.json').write_text(json.dumps(checks, indent=2) + '\n', encoding='utf-8')
    print('BAIQI_CC0_AND_LEGACY_HEAD_VERIFIED_IN_BOTH_FORMS')


if __name__ == '__main__':
    main()
