"""Fit BaiQi wardrobe meshes over the original CC0 body in its own rest space."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from baiqi_mesh_clip import clip_mesh
from lock_baiqi_cc0_body import mesh_fingerprint

WHITE = (.76, .79, .85)
NAVY = (.018, .033, .100)
CHARCOAL = (.047, .041, .061)
GOLD = (.79, .50, .046)
WAIST = .980
HEAD_SCALE = .00865
HEAD_Z = 1.356
LEGACY_NECK_Z = 164.8
NECK_JOIN_Z = 1.350
NECK_COVER_START = 1.315


def head_position(co):
    return Vector((-HEAD_SCALE * co.x + .000255, .029 - HEAD_SCALE * co.y,
                   HEAD_Z + HEAD_SCALE * (co.z - LEGACY_NECK_Z)))


def smoothstep(fraction):
    value = max(0, min(1, fraction))
    return value * value * (3 - 2 * value)


def textile(name, color, source=None, transparent=False):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    surface = nodes['Principled BSDF']
    surface.inputs['Base Color'].default_value = (*color, 1)
    surface.inputs['Roughness'].default_value = .84
    if source:
        art = nodes.new('ShaderNodeTexImage')
        art.image = bpy.data.images.load(str(source), check_existing=True)
        art.extension = 'CLIP'
        uv = nodes.new('ShaderNodeUVMap')
        uv.uv_map = 'Live2D garment artwork'
        links.new(uv.outputs['UV'], art.inputs['Vector'])
        if transparent:
            links.new(art.outputs['Color'], surface.inputs['Base Color'])
            links.new(art.outputs['Alpha'], surface.inputs['Alpha'])
        else:
            mix = nodes.new('ShaderNodeMixRGB')
            mix.inputs[1].default_value = (*color, 1)
            links.new(art.outputs['Alpha'], mix.inputs[0])
            links.new(art.outputs['Color'], mix.inputs[2])
            links.new(mix.outputs[0], surface.inputs['Base Color'])
    return material


def add_thickness(obj, metres):
    modifier = obj.modifiers.new('Cloth thickness', 'SOLIDIFY')
    modifier.thickness = metres
    modifier.offset = -1


def front_factor(point):
    forward = point.y - .016
    return forward / max(.001, math.hypot(point.x, forward))


def corset_top(point):
    return 1.117 - .031 * max(0, front_factor(point)) ** 2


def source_uv(obj, projection, front=None):
    uv = obj.data.uv_layers.new(name='Live2D garment artwork')
    for face in obj.data.polygons:
        if front and not front(face.center):
            face.material_index = 1
        for loop in face.loop_indices:
            point = obj.data.vertices[obj.data.loops[loop].vertex_index].co
            px, py = projection(point)
            uv.data[loop].uv = (px / 1400, 1 - py / 2200)


class Wardrobe:
    def __init__(self, body, destination):
        self.body = body
        self.rig = next(mod.object for mod in body.modifiers if mod.type == 'ARMATURE')
        self.destination = destination
        self.coat = bpy.data.collections.new('BaiQi coat and sleeve accessories')
        destination.children.link(self.coat)
        self.art = ROOT / 'artifacts/baiqi_component_audit/body_layers'
        self.skin_slot = next(slot for slot in body.data.materials if slot.name.endswith('_SKIN'))
        skin_index = body.data.materials.find(self.skin_slot.name)
        body.data.calc_loop_triangles()
        self.skin_triangles = [tri for tri in body.data.loop_triangles if tri.material_index == skin_index]
        self.skin_coords = [body.matrix_world @ vertex.co for vertex in body.data.vertices]
        self.skin = BVHTree.FromPolygons(
            self.skin_coords, [tri.vertices[:] for tri in self.skin_triangles], all_triangles=True,
        )

    def source_material(self, name, color, layer, transparent=False):
        return textile(name, color, self.art / (layer + '.png'), transparent)

    def body_section(self, name, material_suffix, distance, clearance, material, coat=False):
        obj = self.body.copy()
        obj.data = self.body.data.copy()
        obj.name = name
        obj.data.name = name
        (self.coat if coat else self.destination).objects.link(obj)
        obj.hide_select = False
        for prop in list(obj.keys()):
            del obj[prop]
        for modifier in list(obj.modifiers):
            if modifier.type != 'ARMATURE':
                obj.modifiers.remove(modifier)
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world.identity()
        if obj.data.shape_keys:
            obj.shape_key_clear()
        obj.data.transform(world)
        section = next(i for i, slot in enumerate(obj.data.materials) if slot.name.endswith(material_suffix))
        work = bmesh.new()
        work.from_mesh(obj.data)
        bmesh.ops.delete(work, geom=[face for face in work.faces if face.material_index != section], context='FACES')
        bmesh.ops.remove_doubles(work, verts=list(work.verts), dist=.00001)
        work.to_mesh(obj.data)
        work.free()
        for uv in list(obj.data.uv_layers):
            obj.data.uv_layers.remove(uv)
        if distance:
            cuts = distance if isinstance(distance, tuple) else (distance,)
            for cut in cuts:
                clip_mesh(obj, cut)
        obj.data.materials.clear()
        obj.data.materials.append(material)
        normals = [vertex.normal.copy() for vertex in obj.data.vertices]
        for vertex, normal in zip(obj.data.vertices, normals):
            vertex.co += normal * clearance
        for face in obj.data.polygons:
            face.material_index = 0
            face.use_smooth = True
        obj.data.update()
        assert obj.data.polygons, name
        add_thickness(obj, .0007)
        return obj

    def ease_front(self, obj, max_ease):
        for vertex in obj.data.vertices:
            point = vertex.co
            if not 1.105 < point.z < 1.247 or front_factor(point) < .25:
                continue
            # Bridge the crease below the bust with cloth while retaining its contour.
            hit, _, _, _ = self.skin.ray_cast(point + Vector((0, .16, .022)), Vector((0, -1, 0)), .20)
            if hit:
                blend = min(1, (point.z - 1.105) / .019, (1.247 - point.z) / .024)
                point.y += blend * min(max_ease, max(0, hit.y - point.y - .002))
        obj.data.update()

    def upper_body(self):
        def top_cut(point):
            armhole = .140 - .053 * max(0, min(1, (point.z - 1.169) / .112))
            neckline = 1.321 - .019 * max(0, front_factor(point)) ** 3
            return min(point.z - corset_top(point) + .007, neckline - point.z, armhole - abs(point.x))

        blouse = self.body_section('BaiQi fitted sleeveless blouse', '_SKIN', top_cut, .0022,
                                   self.source_material('BaiQi blouse and collar artwork', WHITE, 'shirt'))
        self.ease_front(blouse, .012)
        blouse.data.materials.append(textile('BaiQi off-white blouse back', WHITE))
        source_uv(blouse, lambda p: (700 - p.x * 760, 622 + (1.304 - p.z) * 835),
                  lambda p: front_factor(p) > .08 and abs(p.x) < .081)

        def waist_cut(point):
            hem = WAIST - .010 * (1 - abs(front_factor(point)))
            return min(point.z - hem, corset_top(point) - point.z)

        wrap = self.body_section('BaiQi fitted navy waist wrap', '_SKIN', waist_cut, .0052,
                                 self.source_material('BaiQi navy wrap and source lacing', NAVY, 'girdle'))
        wrap.data.materials.append(textile('BaiQi navy wrap back', NAVY))

        def waist_art(point):
            f = max(0, min(1, (point.z - WAIST) / (corset_top(point) - WAIST)))
            return 700 - point.x * 720, 913 - 143 * f

        source_uv(wrap, waist_art, lambda p: front_factor(p) > .12)
        return blouse, wrap

    def lower_body(self):
        skirt_material = self.source_material('BaiQi pleated skirt artwork', WHITE, 'skirt')
        skirt = self.body_section('BaiQi pleated skirt', '_Bottoms_01_CLOTH', None, .002, skirt_material)
        height = [vertex.co.z for vertex in skirt.data.vertices]
        bottom, top = min(height), max(height)
        for vertex in skirt.data.vertices:
            f = (vertex.co.z - bottom) / (top - bottom)
            vertex.co.z = .752 + f * (1.001 - .752)
            vertex.co.x *= 1.13 - .13 * f
            vertex.co.y = .015 + (vertex.co.y - .015) * (1.10 - .12 * f)
            if vertex.co.z > .855:
                centre = Vector((0, .015, vertex.co.z))
                outward = vertex.co - centre
                radius = outward.length
                outward.normalize()
                hit, _, _, _ = self.skin.ray_cast(centre + .35 * outward, -outward, .35)
                if hit:
                    clearance = .0030 if vertex.co.z > .969 else .006
                    shell = (hit - centre).dot(outward) + clearance
                    draw_in = max(0, (vertex.co.z - .956) / .045)
                    vertex.co = centre + max(radius * (1 - min(1, draw_in)), shell) * outward
        skirt.data.materials.append(textile('BaiQi white rear skirt', WHITE))
        source_uv(skirt, lambda p: (700 - p.x * 990, 918 + (1.001 - p.z) * 1100), lambda p: p.y > .01)

        self.body_section('BaiQi charcoal thigh-high stockings', '_SKIN',
                          lambda p: min(.711 - p.z, p.z - .034), .0025,
                          textile('BaiQi charcoal stocking cloth', (.026, .027, .035)))
        shoe = self.body_section('BaiQi midnight blue shoes', '_Shoes_01_CLOTH', None, .002,
                                textile('BaiQi blue shoe cloth', NAVY))
        shoe.data.materials.append(textile('BaiQi white toe caps', WHITE))
        shoe.data.materials.append(textile('BaiQi gold shoe trim', GOLD))
        for face in shoe.data.polygons:
            if face.center.y > .087 and face.center.z < .042:
                face.material_index = 1
            elif .060 < face.center.z < .066:
                face.material_index = 2

    def outerwear(self):
        dark = textile('BaiQi charcoal coat back', CHARCOAL)

        def coat_cut(point):
            front = max(0, front_factor(point))
            opening = (.052 + .039 * max(0, 1.13 - point.z) / .23) * front ** 4
            upper = 1.325 - .025 * front ** 2
            torso = min(point.z - .908, upper - point.z, abs(point.x) - opening, .193 - abs(point.x))
            sleeve = min(abs(point.x) - .141, .451 - abs(point.x), point.z - 1.155)
            return max(torso, sleeve)

        coat = self.body_section('BaiQi open coat body', '_SKIN', coat_cut, .017,
                                 self.source_material('BaiQi gold-trimmed lapels', CHARCOAL, 'coat_physical'), coat=True)
        self.ease_front(coat, .014)
        coat.data.materials.append(dark)
        source_uv(coat, lambda p: (700 - p.x * 1200, 591 + (1.31 - p.z) * 1280),
                  lambda p: front_factor(p) > .18 and abs(p.x) < .192)
        white = textile('BaiQi white sleeve cuffs', WHITE)
        gold = textile('BaiQi gold cuff edging', GOLD)

        for sign, side in [(-1, 'L'), (1, 'R')]:
            self.body_section(f'BaiQi white cuff {side}', '_SKIN',
                              lambda p: min(sign * p.x - .450, .481 - sign * p.x), .0176, white, coat=True)
            self.body_section(f'BaiQi gold cuff edging {side}', '_SKIN',
                              (lambda p: sign * p.x - .480, lambda p: .486 - sign * p.x), .0176, gold, coat=True)
            self.body_section(f'BaiQi dark wrist band {side}', '_SKIN',
                              lambda p: min(sign * p.x - .519, .541 - sign * p.x, p.z - 1.18),
                              .0034, dark)

    def restore_head(self, previous, original_face):
        prefixes = ('BaiQi crown under hair', 'BaiQi bob front', 'BaiQi rear hair clump',
                    'BaiQi black gold headdress', 'BaiQi round gold glasses', 'BaiQi glasses temple')
        with bpy.data.libraries.load(str(previous)) as (source, target):
            target.objects = ['BaiQi_FemaleFoundation'] + [name for name in source.objects if name.startswith(prefixes)]
        for obj in target.objects:
            assert obj is not None
            is_head = obj.name == 'BaiQi_FemaleFoundation'
            self.destination.objects.link(obj)
            obj.hide_render = False
            obj.hide_set(False)
            obj.parent = None
            obj.matrix_world.identity()
            for modifier in list(obj.modifiers):
                if modifier.type == 'ARMATURE':
                    obj.modifiers.remove(modifier)
                elif modifier.type == 'SOLIDIFY':
                    modifier.thickness *= HEAD_SCALE
            if is_head:
                self.extract_legacy_head(obj)
            for vertex in obj.data.vertices:
                vertex.co = head_position(vertex.co)
            obj.vertex_groups.clear()
            if is_head:
                self.bridge_neck(obj)
                self.fit_neck_join(obj)
            else:
                head = obj.vertex_groups.new(name='J_Bip_C_Head')
                head.add(list(range(len(obj.data.vertices))), 1, 'REPLACE')
            modifier = obj.modifiers.new('Original CC0 head attachment', 'ARMATURE')
            modifier.object = self.rig
        original_face.hide_render = True
        original_face.hide_set(True)
        self.hide_cc0_head_surface()

    def neck_skin_hit(self, point):
        centre = Vector((.000255, -.010, point.z))
        direction = (point - centre).normalized()
        hit, _, index, _ = self.skin.ray_cast(centre + .11 * direction, -direction, .11)
        assert hit is not None, tuple(point)
        return hit, direction, self.skin_triangles[index]

    def bridge_neck(self, obj):
        """Extend the legacy neck rim with connected rings over the source neck."""
        mesh = bmesh.new()
        mesh.from_mesh(obj.data)
        rim = [v for v in mesh.verts if abs(v.co.z - NECK_JOIN_Z) < 2e-6]
        bmesh.ops.remove_doubles(mesh, verts=rim, dist=.000003)
        edges = [edge for edge in mesh.edges if edge.is_boundary
                 and all(abs(v.co.z - NECK_JOIN_Z) < 2e-6 for v in edge.verts)]
        assert edges and all(len([edge for edge in edges if v in edge.verts]) == 2
                             for v in {v for edge in edges for v in edge.verts}), 'Open legacy neck rim'
        links = [(edge.link_loops[0].vert, edge.link_loops[0].link_loop_next.vert) for edge in edges]
        rim = {v for edge in edges for v in edge.verts}
        previous = {vertex: vertex for vertex in rim}
        material_index = obj.data.materials.find('BaiQi Skin')
        for row in range(1, 15):
            z = NECK_JOIN_Z - (NECK_JOIN_Z - NECK_COVER_START) * row / 14
            follow = smoothstep((NECK_JOIN_Z - z) / .013)
            current = {}
            for vertex in rim:
                point = Vector((vertex.co.x, vertex.co.y, z))
                hit, direction, _ = self.neck_skin_hit(point)
                current[vertex] = mesh.verts.new(point.lerp(hit + .0026 * direction, follow))
            for first, second in links:
                face = mesh.faces.new((previous[second], previous[first], current[first], current[second]))
                face.material_index = material_index
                face.smooth = True
            previous = current
        mesh.normal_update()
        mesh.to_mesh(obj.data)
        mesh.free()

    def skin_barycentric(self, point, triangle):
        return barycentric_transform(
            point, *(self.skin_coords[i] for i in triangle.vertices),
            Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)),
        )

    def fit_neck_join(self, obj):
        head = 'J_Bip_C_Head'
        neck = 'J_Bip_C_Neck'
        blend = obj.data.attributes.new('CC0 neck blend', 'FLOAT', 'POINT')
        opacity = obj.data.attributes.new('CC0 neck coverage', 'FLOAT', 'POINT')
        for vertex in obj.data.vertices:
            p = vertex.co
            head_weight = max(0, min(1, (p.z - 1.353) / .027))
            weights = {head: head_weight, neck: 1 - head_weight}
            opacity.data[vertex.index].value = smoothstep((p.z - NECK_COVER_START) / .013)
            if p.z < 1.358:
                hit, _, triangle = self.neck_skin_hit(p)
                barycentric = self.skin_barycentric(hit, triangle)
                follow = smoothstep((1.358 - p.z) / .032)
                blend.data[vertex.index].value = follow
                weights = {name: weight * (1 - follow) for name, weight in weights.items()}
                for i, fraction in zip(triangle.vertices, barycentric):
                    for group in self.body.data.vertices[i].groups:
                        name = self.body.vertex_groups[group.group].name
                        weights[name] = weights.get(name, 0) + follow * max(0, fraction) * group.weight
            total = sum(weights.values())
            for name, weight in weights.items():
                if weight <= 1e-8:
                    continue
                group = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
                group.add([vertex.index], weight / total, 'REPLACE')
        legacy_skin_index = obj.data.materials.find('BaiQi Skin')
        assert legacy_skin_index >= 0
        material = obj.data.materials[legacy_skin_index].copy()
        material.name = 'BaiQi neck junction shading'
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = next(n.image for n in self.skin_slot.node_tree.nodes if n.type == 'TEX_IMAGE')
        hit, _, triangle = self.neck_skin_hit(Vector((.000255, .10, 1.326)))
        uv = self.body.data.uv_layers.active.uv
        u, v = sum((w * uv[loop].vector for w, loop in zip(self.skin_barycentric(hit, triangle), triangle.loops)),
                   Vector((0, 0)))
        coords = nodes.new('ShaderNodeCombineXYZ')
        coords.inputs['X'].default_value = u
        coords.inputs['Y'].default_value = v
        emission = nodes.new('ShaderNodeEmission')
        weight = nodes.new('ShaderNodeAttribute')
        weight.attribute_name = blend.name
        mix = nodes.new('ShaderNodeMixShader')
        links.new(coords.outputs['Vector'], texture.inputs['Vector'])
        links.new(texture.outputs['Color'], emission.inputs['Color'])
        links.new(weight.outputs['Fac'], mix.inputs[0])
        links.new(nodes['Principled BSDF'].outputs['BSDF'], mix.inputs[1])
        links.new(emission.outputs[0], mix.inputs[2])
        coverage = nodes.new('ShaderNodeAttribute')
        coverage.attribute_name = opacity.name
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        fade = nodes.new('ShaderNodeMixShader')
        links.new(coverage.outputs['Fac'], fade.inputs[0])
        links.new(transparent.outputs[0], fade.inputs[1])
        links.new(mix.outputs[0], fade.inputs[2])
        links.new(fade.outputs[0], nodes['Material Output'].inputs['Surface'])
        obj.data.materials[legacy_skin_index] = material

    def extract_legacy_head(self, obj):
        obj.name = 'BaiQi restored authored head and face'
        cut_z = LEGACY_NECK_Z + (NECK_JOIN_Z - HEAD_Z) / HEAD_SCALE
        skin = bmesh.new()
        skin.from_mesh(obj.data)
        source_object = skin.faces.layers.int['anatomy_source_object']
        source_material = skin.faces.layers.int['anatomy_source_material']
        hidden = [face for face in skin.faces if face[source_object] != 1
                  and (face[source_material] != 0 or max(v.co.z for v in face.verts) < cut_z)]
        bmesh.ops.delete(skin, geom=hidden, context='FACES')
        skin.to_mesh(obj.data)
        skin.free()
        clip_mesh(obj, lambda p: p.z - cut_z)

    def hide_cc0_head_surface(self):
        # Remove only the evaluated CC0 scalp. Keep the source body data intact.
        mask = next(mod for mod in self.body.modifiers if mod.type == 'NODES')
        group = mask.node_group
        position = group.nodes.new('GeometryNodeInputPosition')
        transform = group.nodes.new('ShaderNodeVectorRotate')
        transform.rotation_type = 'EULER_XYZ'
        transform.inputs['Rotation'].default_value = self.body.matrix_world.to_euler()
        group.links.new(position.outputs['Position'], transform.inputs['Vector'])
        z = group.nodes.new('ShaderNodeSeparateXYZ')
        group.links.new(transform.outputs['Vector'], z.inputs['Vector'])
        compare = group.nodes.new('FunctionNodeCompare')
        compare.data_type = 'FLOAT'
        compare.operation = 'GREATER_THAN'
        compare.inputs['B'].default_value = 1.336 - self.body.matrix_world.translation.z
        group.links.new(z.outputs['Z'], compare.inputs['A'])
        combine = group.nodes.new('FunctionNodeBooleanMath')
        combine.operation = 'OR'
        invert = next(node for node in group.nodes if node.type == 'BOOLEAN_MATH' and node.operation == 'NOT')
        delete = next(node for node in group.nodes if node.type == 'DELETE_GEOMETRY')
        group.links.new(invert.outputs[0], combine.inputs[0])
        group.links.new(compare.outputs['Result'], combine.inputs[1])
        group.links.new(combine.outputs[0], delete.inputs['Selection'])
        # Clip the visible junction by interpolated rest height. A face-level
        # mask alone leaves corner fragments on the coarse source neck mesh.
        attribute_name = 'CC0 junction rest height'
        attribute = group.nodes.new('GeometryNodeStoreNamedAttribute')
        attribute.data_type = 'FLOAT'
        attribute.domain = 'POINT'
        attribute.inputs['Name'].default_value = attribute_name
        group.links.new(delete.outputs['Geometry'], attribute.inputs['Geometry'])
        group.links.new(z.outputs['Z'], attribute.inputs['Value'])

        skin = self.skin_slot.copy()
        skin.name = 'Original CC0 skin with junction visibility mask'
        nodes = skin.node_tree.nodes
        links = skin.node_tree.links
        height = nodes.new('ShaderNodeAttribute')
        height.attribute_name = attribute_name
        limit = nodes.new('ShaderNodeMath')
        limit.operation = 'GREATER_THAN'
        limit.inputs[1].default_value = 1.330 - self.body.matrix_world.translation.z
        links.new(height.outputs['Fac'], limit.inputs[0])
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        gate = nodes.new('ShaderNodeMixShader')
        terminal = nodes['Material Output'].inputs['Surface']
        links.new(terminal.links[0].from_socket, gate.inputs[1])
        links.new(transparent.outputs[0], gate.inputs[2])
        links.new(limit.outputs[0], gate.inputs[0])
        links.new(gate.outputs[0], terminal)

        assign = group.nodes.new('GeometryNodeSetMaterial')
        assign.inputs['Material'].default_value = skin
        group.links.new(attribute.outputs['Geometry'], assign.inputs['Geometry'])
        terminal = next(node for node in group.nodes if node.type == 'GROUP_OUTPUT')
        group.links.new(assign.outputs['Geometry'], terminal.inputs['Geometry'])
        # Evaluate the seam in rest space so turning the head keeps the same mask.
        self.body.modifiers.move(list(self.body.modifiers).index(mask), 0)

    def add_bow(self, blouse):
        art = self.source_material('BaiQi black and gold bow artwork', CHARCOAL, 'bow_tie', True)
        points = [vertex.co.copy() for vertex in blouse.data.vertices]
        surface = BVHTree.FromPolygons(points, [list(face.vertices) for face in blouse.data.polygons])
        vertices, faces = [], []
        columns, rows = 20, 19
        for row in range(rows):
            for col in range(columns):
                x = -.046 + col * .092 / (columns - 1)
                z = 1.210 + row * .084 / (rows - 1)
                hit, _, _, _ = surface.ray_cast(Vector((x, .25, z)), Vector((0, -1, 0)), .21)
                depth = hit.y if hit else .065
                vertices.append((x, depth + .007, z))
                if row < rows - 1 and col < columns - 1:
                    k = row * columns + col
                    faces.append((k, k + columns, k + columns + 1, k + 1))
        mesh = bpy.data.meshes.new('BaiQi bow tie')
        mesh.from_pydata(vertices, [], faces)
        mesh.materials.append(art)
        obj = bpy.data.objects.new(mesh.name, mesh)
        self.destination.objects.link(obj)
        source_uv(obj, lambda p: (700 - p.x * 1320, 630 + (1.294 - p.z) * 1350))
        group = obj.vertex_groups.new(name='J_Bip_C_UpperChest')
        group.add(list(range(len(vertices))), 1, 'REPLACE')
        modifier = obj.modifiers.new('CC0 chest attachment', 'ARMATURE')
        modifier.object = self.rig
        add_thickness(obj, .0006)


def rest_signature(rig):
    return {bone.name: (bone.parent.name if bone.parent else None, tuple(tuple(row) for row in bone.matrix_local))
            for bone in rig.data.bones}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--locked', required=True, type=Path)
    parser.add_argument('--head-from', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    source = ROOT / args.locked
    lock = json.loads((source.parent / 'cc0_body_lock.json').read_text(encoding='utf-8'))
    bpy.ops.wm.open_mainfile(filepath=str(source))
    body, face = (bpy.data.objects[name] for name in ('Body', 'Face'))
    anatomy = (body, face)
    expected = lock['body_and_face_sha256']
    assert {obj.name: mesh_fingerprint(obj) for obj in anatomy} == expected
    wardrobe = Wardrobe(body, bpy.data.collections['BaiQi external wardrobe'])
    rest = rest_signature(wardrobe.rig)
    transforms = {obj.name: obj.matrix_world.copy() for obj in (*anatomy, wardrobe.rig)}
    blouse, _ = wardrobe.upper_body()
    wardrobe.lower_body()
    wardrobe.outerwear()
    previous = ROOT / args.head_from
    wardrobe.restore_head(previous, face)
    wardrobe.add_bow(blouse)
    bpy.data.orphans_purge(do_recursive=True)
    coat = sorted(obj.name for obj in wardrobe.coat.objects)
    for form in ('coat_on', 'coat_off'):
        for name in coat:
            obj = bpy.data.objects[name]
            obj.hide_render = form == 'coat_off'
            obj.hide_set(form == 'coat_off')
        bpy.context.view_layer.update()
        bpy.ops.file.pack_all()
        destination = output / f'BaiQi_CC0_{form}.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(destination))
        bpy.ops.wm.open_mainfile(filepath=str(destination))
        reopened = bpy.data.objects
        assert {name: mesh_fingerprint(reopened[name]) for name in expected} == expected
        assert rest_signature(reopened[lock['original_rig']]) == rest
        assert all(reopened[name].matrix_world == matrix for name, matrix in transforms.items())
        assert all(reopened[name].hide_render == (form == 'coat_off') for name in coat)
    report = {
        'status': 'fitting_candidate_pending_review',
        'body_and_face_sha256_in_both_forms': expected,
        'cc0_source_file_sha256': lock['source_file_sha256'],
        'restored_authored_head_source_sha256': hashlib.sha256(previous.read_bytes()).hexdigest(),
        'displayed_head': 'Previous BaiQi face, hair, eyewear and headpiece. CC0 Face retained as hidden source reference.',
        'locked_input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'original_skeleton_rest_and_object_transforms_match': True,
        'coat_only': coat,
        'common_external_meshes': sorted(obj.name for obj in bpy.data.collections['BaiQi external wardrobe'].objects),
    }
    (output / 'fitting_report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('BAIQI_CC0_WARDROBE_SAVED')


if __name__ == '__main__':
    main()
