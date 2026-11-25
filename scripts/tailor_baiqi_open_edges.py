"""Build skinned garment bindings and give the detachable coat a longer fall."""
import argparse
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from finish_baiqi_surfaces import COAT, FITTED_TOP
from fit_baiqi_cc0_wardrobe import rest_signature, smoothstep
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint


def boundary_loops(mesh):
    work = bmesh.new()
    work.from_mesh(mesh)
    following, centres = {}, {}
    for edge in work.edges:
        if not edge.is_boundary:
            continue
        use = edge.link_loops[0]
        start, end = use.vert.index, use.link_loop_next.vert.index
        assert start not in following
        following[start] = end
        centres[start] = use.face.calc_center_median()
    work.free()
    rings = []
    while following:
        start = min(following)
        ring = [start]
        next_vertex = following.pop(start)
        while next_vertex != start:
            ring.append(next_vertex)
            next_vertex = following.pop(next_vertex)
        rings.append(ring)
    return rings, centres


def extend_coat(obj, skirt):
    skirt_shell = BVHTree.FromPolygons([vertex.co for vertex in skirt.data.vertices],
                                      [face.vertices[:] for face in skirt.data.polygons])
    for vertex in obj.data.vertices:
        point = vertex.co
        hem = smoothstep((1.035 - point.z) / .14)
        point.z -= .033 * hem
        radial = Vector((point.x, point.y - .016, 0.))
        radius = radial.length
        if hem <= 0 or radius <= .001:
            continue
        centre = Vector((0., .016, point.z))
        azimuth = math.atan2(radial.y, radial.x)
        reach = []
        # Use the widest nearby skirt pleat so the coat keeps its own smooth
        # fall while remaining outside the white skirt underneath.
        for step in (-.20, -.10, 0., .10, .20):
            direction = Vector((math.cos(azimuth + step), math.sin(azimuth + step), 0.))
            contact, _, _, _ = skirt_shell.ray_cast(centre + .32 * direction, -direction, .30)
            if contact is not None:
                reach.append((contact - centre).length)
        target = max(radius + .004 * hem, max(reach, default=0.) + .010)
        point += radial.normalized() * min(.030, target - radius)
    obj.data.update()


def make_binding(source, name, material, choose, width):
    mesh = source.data
    rings, centres = boundary_loops(mesh)
    vertices, faces, origin = [], [], []
    profile = ((-.0003, .0003), (width * .18, .0009), (width * .50, .0012),
               (width * .84, .00085), (width, .00022))
    selected = [ring for ring in rings if choose(ring)]
    assert selected, source.name
    for ring in selected:
        offset = len(vertices)
        for row, index in enumerate(ring):
            prev, nxt = ring[row - 1], ring[(row + 1) % len(ring)]
            anchor = mesh.vertices[index]
            normal = anchor.normal.normalized()
            tangent = mesh.vertices[nxt].co - mesh.vertices[prev].co
            inward = normal.cross(tangent).normalized()
            common_face = (centres[index] + centres[prev]) * .5
            if inward.dot(common_face - anchor.co) < 0:
                inward.negate()
            vertices.extend(anchor.co + inward * distance + normal * lift for distance, lift in profile)
            origin.extend([index] * len(profile))
            current = offset + row * len(profile)
            following = offset + ((row + 1) % len(ring)) * len(profile)
            faces.extend((current + i, following + i, following + i + 1, current + i + 1)
                         for i in range(len(profile) - 1))
    binding = bpy.data.meshes.new(name)
    binding.from_pydata(vertices, [], faces)
    binding.materials.append(material)
    for polygon in binding.polygons:
        polygon.use_smooth = True
    result = bpy.data.objects.new(name, binding)
    source.users_collection[0].objects.link(result)
    result.parent = source.parent
    result.matrix_world = source.matrix_world.copy()
    source_vertices = [mesh.vertices[index] for index in origin]
    groups = [result.vertex_groups.new(name=group.name) for group in source.vertex_groups]
    for index, vertex in enumerate(source_vertices):
        for weight in vertex.groups:
            groups[weight.group].add([index], weight.weight, 'REPLACE')
    for old in source.modifiers:
        if old.type == 'ARMATURE':
            armature = result.modifiers.new(old.name, old.type)
            armature.object = old.object
        elif old.type == 'NODES':
            safety = result.modifiers.new(old.name, old.type)
            safety.node_group = old.node_group
    result.hide_render = source.hide_render
    result.hide_set(source.hide_get())
    return {'loops': len(selected), 'vertices': len(vertices), 'quads': len(faces)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'output/live2d_delta/baiqi_057_surface_finish')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, output = args.source.resolve(), args.out.resolve()
    assert output != source and output.is_relative_to(ROOT)
    pinned = json.loads((source / 'surface_finish.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    report = {}
    for form in ('coat_on', 'coat_off'):
        path = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(path)
        assert source_hash == pinned[form]['candidate_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        objs = bpy.data.objects
        body, head, rig = objs['Body'], objs[HEAD], objs['Armature']
        expected = pinned[form]
        assert mesh_fingerprint(body) == expected['cc0_body_sha256']
        assert mesh_fingerprint(head) == expected['original_head_sha256']
        skeleton = rest_signature(rig)
        blouse, coat = objs[FITTED_TOP], objs[COAT]
        body_hem = min(vertex.co.z for vertex in coat.data.vertices)
        extend_coat(coat, objs['BaiQi pleated skirt'])
        blouse_material = bpy.data.materials['BaiQi off-white blouse back'].copy()
        blouse_material.name = 'BaiQi blouse edge binding'
        node = blouse_material.node_tree.nodes['Principled BSDF']
        node.inputs['Base Color'].default_value = (.683, .72, .78, 1.)
        node.inputs['Roughness'].default_value = .72
        coat_material = bpy.data.materials['BaiQi charcoal coat back'].copy()
        coat_material.name = 'BaiQi removable coat back'
        blouse_binding = make_binding(blouse, 'BaiQi fitted sleeveless binding', blouse_material,
                                      lambda ring: min(blouse.data.vertices[i].co.z for i in ring) > 1.18, .0042)
        coat_binding = make_binding(coat, 'BaiQi open coat binding', coat_material, lambda ring: len(ring) > 70, .0046)
        assert blouse_binding['loops'] == 3 and coat_binding['loops'] == 1
        assert mesh_fingerprint(body) == expected['cc0_body_sha256']
        assert mesh_fingerprint(head) == expected['original_head_sha256'] and rest_signature(rig) == skeleton
        destination = output / path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(destination))
        report[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(destination),
                        'cc0_body_sha256': expected['cc0_body_sha256'], 'original_head_sha256': expected['original_head_sha256'],
                        'coat_hem_drop_mm': 1000 * (body_hem - min(v.co.z for v in coat.data.vertices)),
                        'blouse_binding': blouse_binding, 'coat_binding': coat_binding}
    (output / 'tailoring.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
