"""Fit garment clearance and smooth the authored junction on the posed CC0 rig."""
import argparse
import hashlib
import heapq
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fit_baiqi_cc0_wardrobe import rest_signature, smoothstep, source_uv
from lock_baiqi_cc0_body import mesh_fingerprint


class ClothGraph:
    def __init__(self, name, body):
        self.group = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        self.group.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        self.group.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        self.nodes = self.group.nodes
        self.input = self.nodes.new('NodeGroupInput')
        self.output = self.nodes.new('NodeGroupOutput')
        self.position = self.nodes.new('GeometryNodeInputPosition').outputs['Position']
        body_info = self.nodes.new('GeometryNodeObjectInfo')
        body_info.transform_space = 'RELATIVE'
        body_info.inputs['Object'].default_value = body
        self.body_geometry = body_info.outputs['Geometry']

    def set(self, node, socket, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.group.links.new(value, node.inputs[socket])
        else:
            node.inputs[socket].default_value = value

    def scalar(self, operation, first, second=0.):
        node = self.nodes.new('ShaderNodeMath')
        node.operation = operation
        self.set(node, 0, first)
        self.set(node, 1, second)
        return node.outputs[0]

    def vector(self, operation, first, second=None):
        node = self.nodes.new('ShaderNodeVectorMath')
        node.operation = operation
        self.set(node, 0, first)
        if second is not None:
            self.set(node, 'Scale' if operation == 'SCALE' else 1, second)
        return node.outputs['Vector']

    def attribute(self, name):
        node = self.nodes.new('GeometryNodeInputNamedAttribute')
        node.data_type = 'FLOAT'
        node.inputs['Name'].default_value = name
        return node.outputs['Attribute']

    def target(self, z_range, max_x):
        z = self.attribute('CC0 junction rest height')
        xmin = self.attribute('CC0 cloth fitting lateral rest distance')
        lower = self.scalar('GREATER_THAN', z, z_range[0])
        upper = self.scalar('LESS_THAN', z, z_range[1])
        width = self.scalar('LESS_THAN', xmin, max_x)
        select = self.scalar('MULTIPLY', self.scalar('MULTIPLY', lower, upper), width)
        node = self.nodes.new('GeometryNodeSeparateGeometry')
        node.domain = 'FACE'
        self.set(node, 'Geometry', self.body_geometry)
        self.set(node, 'Selection', select)
        return node.outputs['Selection']

    def normal(self):
        return self.nodes.new('GeometryNodeInputNormal').outputs['Normal']

    def frame(self, anchor):
        info = self.nodes.new('GeometryNodeObjectInfo')
        info.transform_space = 'RELATIVE'
        info.inputs['Object'].default_value = anchor
        return info.outputs

    def dot(self, first, second):
        node = self.nodes.new('ShaderNodeVectorMath')
        node.operation = 'DOT_PRODUCT'
        self.set(node, 0, first)
        self.set(node, 1, second)
        return node.outputs['Value']

    def horizontal(self, vector, up):
        return self.vector('SUBTRACT', vector, self.vector('SCALE', up, self.dot(vector, up)))

    def skirt_drape(self, pelvis, legs):
        frame = self.frame(pelvis)
        rotate = self.nodes.new('FunctionNodeRotateVector')
        self.set(rotate, 'Vector', (0, 0, 1))
        self.set(rotate, 'Rotation', frame['Rotation'])
        up = rotate.outputs[0]
        position = self.vector('SUBTRACT', self.position, frame['Location'])
        radial = self.vector('NORMALIZE', self.horizontal(position, up))
        lifts = []
        for hip, knee, length in legs:
            thigh = self.vector('SUBTRACT', self.frame(knee)['Location'], self.frame(hip)['Location'])
            thigh_up = self.dot(thigh, up)
            rise = self.scalar('MAXIMUM', self.scalar('ADD', thigh_up, length * .97), 0.)
            rise = self.scalar('MINIMUM', self.scalar('MULTIPLY', rise, .56), .136)
            direction = self.vector('NORMALIZE', self.horizontal(thigh, up))
            sector = self.scalar('MAXIMUM', self.scalar('SUBTRACT', self.dot(direction, radial), .32), 0.)
            sector = self.scalar('POWER', self.scalar('MULTIPLY', sector, 1. / .68), 1.85)
            lifts.append(self.scalar('MULTIPLY', rise, sector))
        travel = self.scalar('MULTIPLY', self.scalar('MAXIMUM', *lifts), self.attribute('BaiQi skirt hem lift weight'))
        lift = self.nodes.new('GeometryNodeSetPosition')
        self.set(lift, 'Geometry', self.input.outputs['Geometry'])
        self.set(lift, 'Offset', self.vector('SCALE', up, travel))
        return radial, lift.outputs['Geometry']

    def displace(self, target, normal, search, clearance, limit, geometry=None):
        ray = self.nodes.new('GeometryNodeRaycast')
        self.set(ray, 'Target Geometry', target)
        self.set(ray, 'Source Position', self.vector('ADD', self.position, self.vector('SCALE', normal, search)))
        self.set(ray, 'Ray Direction', self.vector('SCALE', normal, -1.))
        self.set(ray, 'Ray Length', search + clearance)
        distance = self.scalar('SUBTRACT', search + clearance, ray.outputs['Hit Distance'])
        capped = self.scalar('MINIMUM', self.scalar('MAXIMUM', distance, 0.), limit)
        active = self.scalar('MULTIPLY', capped, ray.outputs['Is Hit'])
        node = self.nodes.new('GeometryNodeSetPosition')
        self.set(node, 'Geometry', geometry if geometry is not None else self.input.outputs['Geometry'])
        self.set(node, 'Offset', self.vector('SCALE', normal, active))
        self.set(self.output, 'Geometry', node.outputs['Geometry'])


def expose_rest_lateral(body):
    group = next(mod.node_group for mod in body.modifiers if mod.type == 'NODES')
    node = next(node for node in group.nodes if node.type == 'STORE_NAMED_ATTRIBUTE')
    source = node.inputs['Value'].links[0].from_node
    absolute = group.nodes.new('ShaderNodeMath')
    absolute.operation = 'ABSOLUTE'
    group.links.new(source.outputs['X'], absolute.inputs[0])
    extra = group.nodes.new('GeometryNodeStoreNamedAttribute')
    extra.data_type = 'FLOAT'
    extra.domain = 'POINT'
    extra.inputs['Name'].default_value = 'CC0 cloth fitting lateral rest distance'
    group.links.new(absolute.outputs[0], extra.inputs['Value'])
    material = next(node for node in group.nodes if node.type == 'SET_MATERIAL')
    group.links.new(node.outputs['Geometry'], extra.inputs['Geometry'])
    group.links.new(extra.outputs['Geometry'], material.inputs['Geometry'])


def bind_anchor(rig, bone_name):
    anchor = bpy.data.objects.new('BaiQi skirt frame ' + bone_name, None)
    bpy.context.scene.collection.objects.link(anchor)
    anchor.parent = rig
    anchor.parent_type = 'BONE'
    anchor.parent_bone = bone_name
    bpy.context.view_layer.update()
    anchor.matrix_world = Matrix.Translation(rig.matrix_world @ rig.pose.bones[bone_name].head)
    anchor.hide_set(True)
    return anchor


def put_before_thickness(obj, modifier):
    thickness = next(mod for mod in obj.modifiers if mod.type == 'SOLIDIFY')
    obj.modifiers.move(list(obj.modifiers).index(modifier), list(obj.modifiers).index(thickness))


def make_skirt_panel(obj, body):
    """Rebuild the pleated panel as a closed skirt around the CC0 waist."""
    body_skin = next(index for index, material in enumerate(body.data.materials) if material.name.endswith('_SKIN'))
    hull = BVHTree.FromPolygons([vertex.co for vertex in body.data.vertices],
                               [face.vertices[:] for face in body.data.polygons if face.material_index == body_skin])
    vertices, quads = [], []
    columns, rows = 120, 25
    for row in range(rows):
        fraction = row / (rows - 1)
        z = 1.000 - .248 * fraction
        centre = Vector((0, .015, z))
        for column in range(columns):
            theta = math.tau * column / columns
            direction = Vector((math.sin(theta), math.cos(theta), 0))
            hit = hull.ray_cast(Vector((0, .015, 1.001)) + direction * .23, -direction, .23)[0]
            assert hit is not None
            fitted = (hit - Vector((0, .015, 1.001))).dot(direction) + .0036
            bell = 1 / math.hypot(direction.x / .203, direction.y / .158)
            pleat = .0075 * fraction ** .65 * math.cos(theta * 12)
            radius = fitted * (1 - fraction) + bell * fraction + pleat
            if fraction < .55:
                local = hull.ray_cast(centre + direction * .26, -direction, .26)[0]
                if local:
                    radius = max(radius, (local - centre).dot(direction) + .006 * smoothstep(fraction / .14) + .0036)
            p = centre + direction * radius
            vertices.append(p)
            if row < rows - 1:
                index = row * columns + column
                next_index = row * columns + (column + 1) % columns
                quads.append((index, next_index, next_index + columns, index + columns))
    material_slots = list(obj.data.materials)
    mesh = bpy.data.meshes.new('BaiQi closed pleated skirt panels')
    mesh.from_pydata(vertices, [], quads)
    for material in material_slots:
        mesh.materials.append(material)
    obj.data = mesh
    hem = mesh.attributes.new('BaiQi skirt hem lift weight', 'FLOAT', 'POINT')
    for vertex in mesh.vertices:
        hem.data[vertex.index].value = smoothstep((.991 - vertex.co.z) / .237)
    obj.vertex_groups.clear()
    group = obj.vertex_groups.new(name='J_Bip_C_Hips')
    group.add(list(range(len(vertices))), 1., 'REPLACE')
    for face in mesh.polygons:
        face.use_smooth = True
    mesh.update()
    source_uv(obj, lambda p: (700 - p.x * 990, 918 + (1.001 - p.z) * 1100), lambda p: p.y > .017)


def garments(body, rig):
    expose_rest_lateral(body)
    anchor = bind_anchor(rig, 'J_Bip_C_Hips')
    legs = []
    for side in ('L', 'R'):
        hip, knee = f'J_Bip_{side}_UpperLeg', f'J_Bip_{side}_LowerLeg'
        length = (rig.data.bones[hip].head_local - rig.data.bones[knee].head_local).length
        legs.append((bind_anchor(rig, hip), bind_anchor(rig, knee), length))
    targets = [
        ('BaiQi pleated skirt', (.61, 1.031), .24, .28, .009, .22),
        ('BaiQi fitted sleeveless blouse', (1.067, 1.333), .157, .017, .002, .010),
        ('BaiQi open coat body', (.875, 1.335), .502, .018, .002, .011),
    ]
    for name, z, x, search, clearance, limit in targets:
        obj = bpy.data.objects[name]
        is_skirt = 'skirt' in name
        if is_skirt:
            make_skirt_panel(obj, body)
        graph = ClothGraph(f'{name} clearance from immutable body', body)
        direction, geometry = graph.skirt_drape(anchor, legs) if is_skirt else (graph.normal(), None)
        graph.displace(graph.target(z, x), direction, search, clearance, limit, geometry)
        fit = obj.modifiers.new('Pose-dependent external clearance', 'NODES')
        fit.node_group = graph.group
        put_before_thickness(obj, fit)


def neck(face_reach=.033, transition_start=1.317, lower_transition=.016):
    head = bpy.data.objects['BaiQi restored authored head and face']
    mesh = head.data
    face_slot = mesh.materials.find('BaiQi original face appearance')
    face_vertices = {index for face in mesh.polygons if face.material_index == face_slot for index in face.vertices}
    # Skin the contiguous underside of the head by distance from the painted
    # face. This allows the chin to act as part of the rigid head during turns.
    key = [tuple(round(value, 6) for value in vertex.co) for vertex in mesh.vertices]
    graph = {point: {} for point in key}
    for edge in mesh.edges:
        a, b = edge.vertices
        length = (mesh.vertices[a].co - mesh.vertices[b].co).length
        graph[key[a]][key[b]] = graph[key[b]][key[a]] = length
    distance = {key[index]: 0. for index in face_vertices}
    queue = [(0., point) for point in distance]
    heapq.heapify(queue)
    while queue:
        length, current = heapq.heappop(queue)
        if length != distance[current]:
            continue
        for neighbour, edge_length in graph[current].items():
            length_to_point = length + edge_length
            if length_to_point < face_reach and length_to_point < distance.get(neighbour, float('inf')):
                distance[neighbour] = length_to_point
                heapq.heappush(queue, (length_to_point, neighbour))
    head_group = head.vertex_groups['J_Bip_C_Head']
    neck_group = head.vertex_groups['J_Bip_C_Neck']
    for vertex in mesh.vertices:
        height = vertex.co.z
        if height <= transition_start and vertex.index not in face_vertices:
            continue
        existing = {group.group: group.weight for group in vertex.groups}
        to_face = distance.get(key[vertex.index], face_reach)
        head_weight = max(1 - smoothstep(to_face / face_reach), smoothstep((height - 1.324) / .070))
        # At the lower edge retain the base-neck weighting. Give the whole
        # original face, including its lower jaw and mouth, full head weight.
        if vertex.index in face_vertices:
            head_weight = 1.
        elif height < transition_start + lower_transition:
            ramp = smoothstep((height - transition_start) / lower_transition)
            head_weight = existing.get(head_group.index, 0.) * (1 - ramp) + head_weight * ramp
        previous = sum(weight for index, weight in existing.items() if index != head_group.index)
        if previous > 1e-9:
            for index, weight in existing.items():
                if index != head_group.index:
                    head.vertex_groups[index].add([vertex.index], (1 - head_weight) * weight / previous, 'REPLACE')
        elif head_weight < 1:
            neck_group.add([vertex.index], 1 - head_weight, 'REPLACE')
        head_group.add([vertex.index], head_weight, 'REPLACE')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    base = ROOT / args.candidate
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    for form in ('coat_on', 'coat_off'):
        name = f'BaiQi_CC0_{form}.blend'
        source = base / name
        bpy.ops.wm.open_mainfile(filepath=str(source))
        body = bpy.data.objects['Body']
        rig = bpy.data.objects['Armature']
        expected = mesh_fingerprint(body)
        rest = rest_signature(rig)
        garments(body, rig)
        neck()
        bpy.context.view_layer.update()
        assert expected == mesh_fingerprint(body)
        assert rest == rest_signature(rig)
        path = output / name
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        records[form] = {'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                         'model_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'body_sha256': expected, 'neck_face_vertices_protected': True}
    (output / 'clearance_report.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
