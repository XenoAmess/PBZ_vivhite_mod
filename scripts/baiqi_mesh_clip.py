"""Clip skinned triangles against a signed boundary, preserving UVs and weights."""
import bpy
from mathutils import Vector


def clip_mesh(obj, signed_distance):
    mesh = obj.data
    mesh.calc_loop_triangles()
    layers = list(mesh.uv_layers)
    vertices, faces, face_uvs, face_materials, weights = [], [], [], [], []
    lookup = {}

    def corner(vertex_index, loop_index):
        vertex = mesh.vertices[vertex_index]
        return {
            'co': vertex.co.copy(),
            'uv': [Vector(layer.uv[loop_index].vector) for layer in layers],
            'weights': {group.group: group.weight for group in vertex.groups},
        }

    def interpolate(a, b, fraction):
        groups = a['weights'].keys() | b['weights'].keys()
        return {
            'co': a['co'].lerp(b['co'], fraction),
            'uv': [first.lerp(second, fraction) for first, second in zip(a['uv'], b['uv'])],
            'weights': {
                index: a['weights'].get(index, 0) * (1 - fraction) + b['weights'].get(index, 0) * fraction
                for index in groups
            },
        }

    for triangle in mesh.loop_triangles:
        polygon = [corner(vertex, loop) for vertex, loop in zip(triangle.vertices, triangle.loops)]
        clipped = []
        for index, current in enumerate(polygon):
            previous = polygon[index - 1]
            inside = signed_distance(current['co']) >= 0
            was_inside = signed_distance(previous['co']) >= 0
            if inside != was_inside:
                lower, upper = 0., 1.
                for _ in range(20):
                    middle = (lower + upper) / 2
                    coordinate = previous['co'].lerp(current['co'], middle)
                    if (signed_distance(coordinate) >= 0) == was_inside:
                        lower = middle
                    else:
                        upper = middle
                clipped.append(interpolate(previous, current, (lower + upper) / 2))
            if inside:
                clipped.append(current)
        if len(clipped) < 3:
            continue
        indices = []
        for vertex in clipped:
            key = tuple(round(value, 6) for value in vertex['co'])
            key += tuple(round(value, 6) for uv in vertex['uv'] for value in uv)
            if key not in lookup:
                lookup[key] = len(vertices)
                vertices.append(vertex['co'])
                weights.append(vertex['weights'])
            indices.append(lookup[key])
        if len(set(indices)) < 3:
            continue
        faces.append(indices)
        face_uvs.append([vertex['uv'] for vertex in clipped])
        face_materials.append(triangle.material_index)

    result = bpy.data.meshes.new(obj.name + ' fitted boundaries')
    result.from_pydata(vertices, [], faces)
    for material in mesh.materials:
        result.materials.append(material)
    result_layers = [result.uv_layers.new(name=layer.name) for layer in layers]
    for polygon, uvs, material in zip(result.polygons, face_uvs, face_materials):
        polygon.material_index = material
        polygon.use_smooth = True
        for loop, corner_uv in zip(polygon.loop_indices, uvs):
            for layer, uv in zip(result_layers, corner_uv):
                layer.uv[loop].vector = uv

    names = list(obj.vertex_groups.keys())
    obj.data = result
    obj.vertex_groups.clear()
    for name in names:
        obj.vertex_groups.new(name=name)
    for index, contributions in enumerate(weights):
        total = sum(contributions.values())
        assert total > 0
        for group, weight in contributions.items():
            if weight / total > 1e-7:
                obj.vertex_groups[group].add([index], weight / total, 'REPLACE')
