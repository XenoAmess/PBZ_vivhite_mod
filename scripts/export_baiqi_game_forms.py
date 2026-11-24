"""Prepare adult-only skeletal-mesh inputs for the two fitted BaiQi forms."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tools/blender_libs'),
                str(ROOT / 'vendor/UEFormat/plugins/blender')]

from baiqi_mesh_clip import clip_mesh
from fit_baiqi_cc0_wardrobe import rest_signature
from io_scene_ueformat.importer.import_context import UEFormatImport
from io_scene_ueformat.options import UEModelOptions
from lock_baiqi_cc0_body import mesh_fingerprint
from probe_baiqi_native_bridge import add_branch, NECK_CARRIER


def isolate_skin(obj):
    if obj.data.shape_keys:
        obj.shape_key_clear()
    skin = next(index for index, material in enumerate(obj.data.materials) if material.name.endswith('_SKIN'))
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    bmesh.ops.delete(mesh, geom=[face for face in mesh.faces if face.material_index != skin], context='FACES')
    mesh.to_mesh(obj.data)
    mesh.free()
    clip_mesh(obj, lambda p: 1.330 - p.z)
    material = obj.data.materials[skin]
    obj.data.materials.clear()
    obj.data.materials.append(material)


def export_mesh(obj, native, names):
    duplicate = obj.copy()
    duplicate.data = obj.data.copy()
    duplicate.name = obj.name + ' export'
    bpy.context.scene.collection.objects.link(duplicate)
    duplicate.hide_select = False
    duplicate.hide_set(False)
    world = duplicate.matrix_world.copy()
    duplicate.parent = None
    duplicate.matrix_world.identity()
    duplicate.data.transform(world, shape_keys=True)
    duplicate.modifiers.clear()
    if obj.name == 'Body':
        isolate_skin(duplicate)
    game_uv(duplicate.data)
    if obj.name == 'BaiQi pleated skirt':
        merge_skirt_material(duplicate.data)
    if obj.name == 'BaiQi restored authored head and face':
        junction_color(duplicate.data)
    duplicate.data.transform(Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Scale(100., 4), shape_keys=True)
    for group in list(duplicate.vertex_groups):
        if group.name not in names:
            raise ValueError(f'Unmapped bone group {group.name} on {obj.name}')
        group.name = names[group.name]
    duplicate.parent = native
    skinning = duplicate.modifiers.new('Original CC0 skin weights on deform branch', 'ARMATURE')
    skinning.object = native
    return duplicate


def merge_skirt_material(mesh):
    # A single closed section lets Chaos solve across the rear/front joins.
    # Bottom-left texels sit outside the artwork and use the white fallback.
    layer = mesh.uv_layers[0]
    for face in mesh.polygons:
        if face.material_index > 0:
            for index in face.loop_indices:
                layer.uv[index].vector = (.012, .012)
            face.material_index = 0
    for index in range(len(mesh.materials) - 1, 0, -1):
        mesh.materials.pop(index=index)


def first_texture(material):
    if material.use_nodes:
        return next((node for node in material.node_tree.nodes if node.type == 'TEX_IMAGE' and node.image), None)
    return None


def projected_uv(texture):
    scale = Vector((1., 1., 1.))
    offset = Vector((0., 0., 0.))
    node = texture.inputs['Vector'].links[0].from_node if texture.inputs['Vector'].is_linked else None
    while node is not None and node.type == 'VECT_MATH' and node.operation in {'ADD', 'MULTIPLY'}:
        adjustment = Vector(node.inputs[1].default_value)
        if node.operation == 'ADD':
            offset += scale * adjustment
        else:
            scale *= adjustment
        node = node.inputs[0].links[0].from_node if node.inputs[0].is_linked else None
    return (node.uv_map if node is not None and node.type == 'UVMAP' else None), scale, offset


def game_uv(mesh):
    if not mesh.uv_layers:
        return
    mapping = []
    for material in mesh.materials:
        node = first_texture(material)
        name, scale, offset = projected_uv(node) if node else (None, Vector((1, 1, 1)), Vector((0, 0, 0)))
        coordinates = mesh.uv_layers.get(name) if name else mesh.uv_layers[0]
        mapping.append((coordinates, scale, offset))
    values = [None] * len(mesh.loops)
    for face in mesh.polygons:
        coordinates, scale, offset = mapping[face.material_index]
        if coordinates is None:
            coordinates = mesh.uv_layers[0]
        for index in face.loop_indices:
            u, v = coordinates.uv[index].vector
            values[index] = (u * scale.x + offset.x, v * scale.y + offset.y)
    for layer in list(mesh.uv_layers):
        mesh.uv_layers.remove(layer)
    layer = mesh.uv_layers.new(name='BaiQi game UV')
    for index, value in enumerate(values):
        layer.uv[index].vector = value


def srgb_to_linear(channel):
    return channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4


def sample_rgb(texture):
    assert texture.inputs['Vector'].is_linked
    point = texture.inputs['Vector'].links[0].from_node
    assert point.type == 'COMBXYZ'
    image = texture.image
    x = int(point.inputs['X'].default_value * image.size[0])
    y = int(point.inputs['Y'].default_value * image.size[1])
    index = 4 * (y * image.size[0] + x)
    return list(image.pixels[index:index + 3])


def junction_color(mesh):
    material = mesh.materials['BaiQi neck junction shading']
    textures = [node for node in material.node_tree.nodes if node.type == 'TEX_IMAGE']
    assert len(textures) == 2
    neck, arms = [Vector(tuple(srgb_to_linear(channel) for channel in sample_rgb(texture))) for texture in textures]
    blend = mesh.attributes['CC0 neck blend'].data
    coverage = mesh.attributes['CC0 neck coverage'].data
    layer = mesh.color_attributes.new(name='BaiQi junction pigment and coverage', type='FLOAT_COLOR', domain='POINT')
    for i, vertex in enumerate(layer.data):
        vertex.color = (*arms.lerp(neck, blend[i].value), coverage[i].value)
    mesh.color_attributes.active_color = layer


def retain_drivers(native, names, reserved=1):
    """Keep control joints present in the runtime pose despite no visible weights."""
    vertices, faces = [], []
    for index in range(len(names)):
        offset = (index % 29) * .055
        row = (index // 29) * .055
        start = len(vertices)
        vertices.extend([(offset, row, .04), (offset + .025, row, .04), (offset, row + .025, .04)])
        faces.append((start, start + 1, start + 2))
    mesh = bpy.data.meshes.new('BaiQi native driver retention triangles')
    mesh.from_pydata(vertices, [], faces)
    marker = bpy.data.objects.new(mesh.name, mesh)
    bpy.context.scene.collection.objects.link(marker)
    marker.parent = native
    for index in range(reserved):
        material = bpy.data.materials.new(f'BaiQi invisible driver section {index:02}')
        material.diffuse_color = (0, 0, 0, 0)
        mesh.materials.append(material)
    for index, face in enumerate(mesh.polygons):
        face.material_index = index % reserved
    for index, name in enumerate(names):
        marker.vertex_groups.new(name=name).add(list(range(3 * index, 3 * index + 3)), 1., 'REPLACE')
    modifier = marker.modifiers.new('Native driver skinning', 'ARMATURE')
    modifier.object = native
    return marker


def packed_materials(meshes, output):
    directory = output / 'textures'
    directory.mkdir(exist_ok=True)
    records = {}
    for material in sorted({material for mesh in meshes for material in mesh.data.materials}, key=lambda m: m.name):
        images = []
        if material.use_nodes:
            for node in material.node_tree.nodes:
                if node.type != 'TEX_IMAGE' or node.image is None or not node.image.packed_file:
                    continue
                payload = node.image.packed_file.data
                digest = hashlib.sha256(payload).hexdigest()
                suffix = '.png' if payload.startswith(b'\x89PNG\r\n\x1a\n') else '.jpg'
                path = directory / (digest[:20] + suffix)
                if not path.exists():
                    path.write_bytes(payload)
                images.append({'node': node.name, 'label': node.label, 'image': node.image.name,
                               'path': path.relative_to(output).as_posix(), 'sha256': digest})
        shader = material.node_tree.nodes.get('Principled BSDF') if material.use_nodes else None
        color = shader.inputs['Base Color'].default_value if shader else material.diffuse_color
        fallback = list(color)
        is_face = material.name == 'BaiQi original face appearance'
        record = {'images': images, 'fallback_rgba': fallback,
                  'type': 'masked' if shader and shader.inputs['Alpha'].is_linked else 'opaque'}
        if is_face:
            texture_nodes = [node for node in material.node_tree.nodes if node.type == 'TEX_IMAGE']
            record.update(type='skin_face', arm_sample=sample_rgb(texture_nodes[2]), face_sample=sample_rgb(texture_nodes[3]))
        elif material.name == 'BaiQi neck junction shading':
            record['type'] = 'skin_junction'
        elif material.name.endswith('_SKIN'):
            record['type'] = 'skin_body'
        elif material.name.startswith('BaiQi invisible driver section'):
            record['type'] = 'hidden'
        records[material.name] = record
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--reserve-native-slots', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    candidate = ROOT / args.candidate
    output = ROOT / args.out
    output.mkdir(parents=True, exist_ok=True)
    rows = {}
    for form in ('coat_on', 'coat_off'):
        source = candidate / f'BaiQi_CC0_{form}.blend'
        bpy.ops.wm.open_mainfile(filepath=str(source))
        body = bpy.data.objects['Body']
        original = mesh_fingerprint(body)
        assert original == body['baiqi_cc0_geometry_sha256']
        cc0 = bpy.data.objects['Armature']
        meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and not obj.hide_render]
        cc0.name = 'Original CC0 pose reference'
        before = set(bpy.data.objects)
        UEFormatImport(UEModelOptions(scale_factor=1., reorient_bones=False, import_sockets=False,
                                      import_morph_targets=False)).import_file(ROOT / 'repro/game_reference/Hun_Body_Simple.uemodel')
        imported = set(bpy.data.objects) - before
        native = next(obj for obj in imported if obj.type == 'ARMATURE')
        native.name = 'Armature'
        for obj in imported:
            if obj.type == 'MESH':
                bpy.data.objects.remove(obj, do_unlink=True)
        native_rest = rest_signature(native)
        aliases = add_branch(native, cc0)
        native_plus_cc0 = rest_signature(native)
        assert {name: native_plus_cc0[name][0] for name in native_rest} == {n: v[0] for n, v in native_rest.items()}
        assembled = [export_mesh(obj, native, aliases) for obj in meshes]
        reserved = 18 if args.reserve_native_slots else 1
        driver = retain_drivers(native, [*native_rest, NECK_CARRIER], reserved)
        assembled.append(driver)
        if args.reserve_native_slots:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in assembled:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = driver
            bpy.ops.object.join()
            assembled = [driver]
            assert all(material.name.startswith('BaiQi invisible driver section') for material in driver.data.materials[:reserved])
        bpy.ops.object.select_all(action='DESELECT')
        for obj in [native, *assembled]:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = native
        scene = bpy.context.scene
        scene.unit_settings.system = 'METRIC'
        scene.unit_settings.scale_length = .01
        path = output / f'BaiQi_Adult_{form}.fbx'
        bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, add_leaf_bones=False, bake_anim=False,
                                 use_mesh_modifiers=False, mesh_smooth_type='FACE', object_types={'ARMATURE', 'MESH'},
                                 armature_nodetype='NULL', use_armature_deform_only=False)
        assert mesh_fingerprint(body) == original
        rows[form] = {'fbx': str(path), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                      'body_sha256': original, 'native_bones': len(native_rest), 'cc0_bones': len(aliases),
                      'reserved_native_slots': reserved,
                      'visible_meshes': [obj.name for obj in meshes], 'materials': packed_materials(assembled, output)}
    (output / 'form_inputs.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
    print('BAIQI_ADULT_FORM_MESH_INPUTS_READY')


if __name__ == '__main__':
    main()
