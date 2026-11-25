"""Sample the authored head's nose normals and tangent axes in the original face UVs."""
import argparse
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from export_baiqi_game_forms import game_uv
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint


FACE = 'BaiQi original face appearance'
BOX = (397, 432, 466, 547)
UNITS = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))


def sample_basis(mesh):
    game_uv(mesh)
    mesh.calc_loop_triangles()
    mesh.calc_tangents(uvmap=mesh.uv_layers.active.name)
    slot = mesh.materials.find(FACE)
    assert slot >= 0
    triangles = [tuple(t.loops) for t in mesh.loop_triangles if t.material_index == slot]
    uv = mesh.uv_layers.active.uv
    points = [Vector((uv[i].vector.x * 880., (1. - uv[i].vector.y) * 800.,
                      mesh.vertices[loop.vertex_index].co.y * 1000.)) for i, loop in enumerate(mesh.loops)]
    overlap = BVHTree.FromPolygons(points, triangles, all_triangles=True)
    normal = np.array([corner.vector[:] for corner in mesh.corner_normals])
    tangent = np.array([loop.tangent[:] for loop in mesh.loops])
    bitangent = np.cross(normal, tangent) * np.array([loop.bitangent_sign for loop in mesh.loops])[:, None]
    axes = np.stack((normal, tangent, bitangent), axis=1)
    left, top, right, bottom = BOX
    vertical = np.zeros((bottom - top, right - left, 3), dtype=np.float32)
    horizontal = np.zeros_like(vertical)
    down = Vector((0, 0, -1))
    for row in range(top, bottom):
        for column in range(left, right):
            hit, _, index, _ = overlap.ray_cast(Vector((column + .5, row + .5, 250.)), down, 500.)
            assert hit is not None, (column, row)
            ids = triangles[index]
            weights = np.array(barycentric_transform(hit, *(points[i] for i in ids), *UNITS))
            interpolated = np.sum(axes[list(ids)] * weights[:, None, None], axis=0)
            assert np.all(np.linalg.norm(interpolated, axis=1) > .5)
            lengths = np.linalg.norm(interpolated, axis=1)
            vertical[row - top, column - left] = interpolated[:, 2] / lengths
            horizontal[row - top, column - left] = interpolated[:, 0] / lengths
    return vertical, horizontal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, destination = ((ROOT / path).resolve() for path in (args.source, args.source_inputs, args.out))
    assert destination.is_relative_to(ROOT)
    form_inputs = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    basis = None
    geometry = None
    for form in ('coat_off', 'coat_on'):
        path = source / f'BaiQi_CC0_{form}.blend'
        assert fingerprint(path) == form_inputs[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        head = bpy.data.objects[HEAD]
        assert head.matrix_world.is_identity
        current = mesh_fingerprint(head)
        if basis is None:
            geometry = current
            data = head.data.copy()
            basis = sample_basis(data)
            bpy.data.meshes.remove(data)
        else:
            assert geometry == current
    destination.parent.mkdir(parents=True, exist_ok=True)
    vertical, horizontal = basis
    np.savez_compressed(destination, box=BOX, vertical=vertical, horizontal=horizontal, head_sha256=geometry)
    print('BAIQI_NOSE_UV_BASIS', BOX, float(vertical[..., 0].min()), geometry, flush=True)


if __name__ == '__main__':
    main()
