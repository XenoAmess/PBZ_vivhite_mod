"""Create a fitting file with untouched CC0 anatomy and a reversible outfit mask."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np


def mesh_fingerprint(obj, material_names=None):
    mesh = obj.data
    digest = hashlib.sha256()
    positions = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', positions)
    digest.update(positions.tobytes())
    for face in mesh.polygons:
        digest.update(np.array([face.material_index, len(face.vertices), *face.vertices], dtype=np.int32).tobytes())
    for uv_layer in mesh.uv_layers:
        digest.update(uv_layer.name.encode())
        uv = np.empty(len(uv_layer.uv) * 2, dtype=np.float32)
        uv_layer.uv.foreach_get('vector', uv)
        digest.update(uv.tobytes())
    for name in (material_names if material_names is not None else [material.name for material in mesh.materials]):
        digest.update(name.encode())
    for group in obj.vertex_groups:
        digest.update(group.name.encode())
    for vertex in mesh.vertices:
        digest.update(np.array([(g.group, g.weight) for g in vertex.groups], dtype=np.float64).tobytes())
    if mesh.shape_keys:
        for key in mesh.shape_keys.key_blocks:
            digest.update(key.name.encode())
            coordinates = np.empty(len(key.data) * 3, dtype=np.float32)
            key.data.foreach_get('co', coordinates)
            digest.update(coordinates.tobytes())
    return digest.hexdigest()



def main():
    ROOT = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='artifacts/anatomy_base/Base_Female.blend')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source = ROOT / args.base
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(source))
    body = bpy.data.objects['Body']
    face = bpy.data.objects['Face']
    fingerprints = {obj.name: mesh_fingerprint(obj) for obj in (body, face)}
    original_mesh_sizes = {obj.name: len(obj.data.vertices) for obj in (body, face)}
    original_rig = next(mod.object for mod in body.modifiers if mod.type == 'ARMATURE')
    assert original_rig == next(mod.object for mod in face.modifiers if mod.type == 'ARMATURE')

    # Factory clothing and hair live in the same imported mesh as the body.
    # Suppress those material sections only in the evaluated preview.
    visible_skin = next(material for material in body.data.materials if material.name.endswith('_SKIN'))
    group = bpy.data.node_groups.new('BaiQi fitting visibility for CC0 factory outfit', 'GeometryNodeTree')
    group.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    group.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    inputs = group.nodes.new('NodeGroupInput')
    outputs = group.nodes.new('NodeGroupOutput')
    select = group.nodes.new('GeometryNodeMaterialSelection')
    select.inputs['Material'].default_value = visible_skin
    invert = group.nodes.new('FunctionNodeBooleanMath')
    invert.operation = 'NOT'
    delete = group.nodes.new('GeometryNodeDeleteGeometry')
    delete.domain = 'FACE'
    group.links.new(inputs.outputs['Geometry'], delete.inputs['Geometry'])
    group.links.new(select.outputs['Selection'], invert.inputs[0])
    group.links.new(invert.outputs[0], delete.inputs['Selection'])
    group.links.new(delete.outputs['Geometry'], outputs.inputs['Geometry'])
    modifier = body.modifiers.new('Visibility only: hide factory outfit', 'NODES')
    modifier.node_group = group

    for obj in (body, face):
        obj.hide_select = True
        obj['baiqi_cc0_geometry_sha256'] = fingerprints[obj.name]
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and obj not in (body, face):
            obj.hide_render = True
            obj.hide_set(True)

    wardrobe = bpy.data.collections.new('BaiQi external wardrobe')
    bpy.context.scene.collection.children.link(wardrobe)
    assert all(mesh_fingerprint(obj) == fingerprints[obj.name] for obj in (body, face))
    assert all(len(obj.data.vertices) == original_mesh_sizes[obj.name] for obj in (body, face))
    path = output / 'BaiQi_CC0_Fitting.blend'
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    report = {
        'source': source.relative_to(ROOT).as_posix(),
        'source_file_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'locked_file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'body_and_face_sha256': fingerprints,
        'original_mesh_vertex_counts': original_mesh_sizes,
        'original_rig': original_rig.name,
        'note': 'Body and Face geometry, UVs, shape keys, material slots and skinning weights remain from the original CC0 asset. The display modifier hides factory garment surfaces in evaluation only.',
    }
    (output / 'cc0_body_lock.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('BAIQI_CC0_BASE_LOCKED', fingerprints)


if __name__ == '__main__':
    main()
