"""Clip skinned triangles against a signed boundary, preserving UVs and weights."""
import bpy
from mathutils import Vector


def clip_mesh(obj, signed_distance, *, texture_space=False, refine_edges=False, conform_edges=False):
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

    def distance(vertex):
        return signed_distance(vertex['uv'][0] if texture_space else vertex['co'])

    def refined(corners):
        if not refine_edges:
            return [corners]
        a, b, c = corners
        ab, bc, ca = interpolate(a, b, .5), interpolate(b, c, .5), interpolate(c, a, .5)
        samples = [distance(vertex) >= 0 for vertex in (a, b, c, ab, bc, ca)]
        if all(samples):
            return [corners]
        if not any(samples):
            center = interpolate(ab, c, 1. / 3.)
            return [(a, b, center), (b, c, center), (c, a, center)] if distance(center) >= 0 else []
        return [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]

    def source_triangles():
        for triangle in mesh.loop_triangles:
            corners = [corner(vertex, loop) for vertex, loop in zip(triangle.vertices, triangle.loops)]
            yield triangle, corners, refined(corners)

    def partitions():
        if not conform_edges:
            for triangle, _, polygons in source_triangles():
                yield triangle.material_index, polygons
            return

        # Match shared midpoints so cut surfaces retain continuous smoothing.
        planned = []
        split_edges = set()
        for triangle, corners, polygons in source_triangles():
            a, b, c = triangle.vertices[:]
            edges = [tuple(sorted(pair)) for pair in ((a, b), (b, c), (c, a))]
            if len(polygons) == 4:
                split_edges.update(edges)
            planned.append((triangle.material_index, corners, polygons, edges))

        for material_index, corners, polygons, edges in planned:
            if len(polygons) == 1 and polygons[0] is corners and any(edge in split_edges for edge in edges):
                boundary = []
                for index, edge in enumerate(edges):
                    start, end = corners[index], corners[(index + 1) % 3]
                    boundary.append(start)
                    if edge in split_edges:
                        boundary.append(interpolate(start, end, .5))
                a, b, c = corners
                center = interpolate(interpolate(a, b, .5), c, 1. / 3.)
                polygons = [(start, end, center) for start, end in zip(boundary, boundary[1:] + boundary[:1])]
            yield material_index, polygons

    for material_index, polygons in partitions():
        for polygon in polygons:
            clipped = []
            distances = [distance(vertex) for vertex in polygon]
            for index, current in enumerate(polygon):
                previous = polygon[index - 1]
                inside = distances[index] >= 0
                was_inside = distances[index - 1] >= 0
                if inside != was_inside:
                    lower, upper = 0., 1.
                    for _ in range(15 if texture_space else 20):
                        middle = (lower + upper) / 2
                        coordinate = interpolate(previous, current, middle)
                        if (distance(coordinate) >= 0) == was_inside:
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
            if conform_edges:
                distinct = [index for index in range(len(indices)) if indices[index] != indices[index - 1]]
                indices = [indices[index] for index in distinct]
                clipped = [clipped[index] for index in distinct]
            if len(set(indices)) < 3:
                continue
            faces.append(indices)
            face_uvs.append([vertex['uv'] for vertex in clipped])
            face_materials.append(material_index)

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
