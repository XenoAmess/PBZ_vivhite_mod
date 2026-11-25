"""Refit the neutral closed mouth to the original BaiQi lip artwork."""
import argparse
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import delaunay_2d_cdt


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from export_baiqi_game_forms import game_uv
from fit_baiqi_cc0_wardrobe import rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint


def smooth(value):
    t=np.clip(value,0.,1.)
    return t*t*(3.-2.*t)

def ordered_ring(edges):
    graph = {}
    for edge in edges:
        a, b = edge.verts
        graph.setdefault(a, []).append(b)
        graph.setdefault(b, []).append(a)
    assert all(len(neighbors) == 2 for neighbors in graph.values())
    first = min(graph, key=lambda vertex: vertex.index)
    previous, vertex = first, min(graph[first], key=lambda vertex: vertex.index)
    loop = [first]
    while vertex != first:
        loop.append(vertex)
        following = next(neighbor for neighbor in graph[vertex] if neighbor != previous)
        previous, vertex = vertex, following
        assert len(loop) <= len(graph)
    assert len(loop) == len(graph)
    return loop


def surface_tree(faces):
    vertices = list(dict.fromkeys(vertex for face in faces for vertex in face.verts))
    indices = {vertex: index for index, vertex in enumerate(vertices)}
    return BVHTree.FromPolygons([vertex.co for vertex in vertices],
                                [[indices[vertex] for vertex in face.verts] for face in faces])


def refit_mouth(head, volume_scale):
    recess = .72
    lower_volume, upper_volume = .55 * volume_scale, .31 * volume_scale
    mesh = head.data
    projected = mesh.copy()
    game_uv(projected)
    projected.calc_loop_triangles()
    slot = projected.materials.find('BaiQi original face appearance')
    uv = projected.uv_layers.active.uv
    points = [Vector((point.vector.x * 880., (1. - point.vector.y) * 800.,
                      mesh.vertices[loop.vertex_index].co.y * 1000.))
              for loop, point in zip(projected.loops, uv, strict=True)]
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    components = []
    visited = set()
    for vertex in bm.verts:
        if vertex.index in visited:
            continue
        component = set()
        stack = [vertex]
        while stack:
            vertex = stack.pop()
            if vertex.index in visited:
                continue
            component.add(vertex.index)
            visited.add(vertex.index)
            stack.extend(edge.other_vert(vertex) for edge in vertex.link_edges)
        components.append(component)
    main = max(components, key=len)
    front_uv = {projected.loops[index].vertex_index: points[index]
                for triangle in projected.loop_triangles if triangle.material_index == slot
                for index in triangle.loops}

    def belongs_to_slit(vertex):
        u, v, depth = front_uv.get(vertex.index, (0., 0., 0.))
        return vertex.index in main and 403. < u < 455. and 539. < v < 543. and depth > 69.
    slit_edges = [edge for edge in bm.edges if edge.is_boundary and all(belongs_to_slit(v) for v in edge.verts)]
    assert len(slit_edges) == 64
    slit = ordered_ring(slit_edges)
    tris = [tuple(triangle.loops) for triangle in projected.loop_triangles
            if triangle.material_index == slot and triangle.vertices[0] in main]
    surface = BVHTree.FromPolygons(points, tris, all_triangles=True)
    mapping = {projected.loops[index].vertex_index: np.asarray(points[index])[:2]
               for triangle in tris for index in triangle}
    bpy.data.meshes.remove(projected)
    interior = [face for face in bm.faces if face.material_index == slot and face.verts[0].index not in main
                and all(384. < front_uv[vertex.index][0] < 478. and 509. < front_uv[vertex.index][1] < 561.
                        for vertex in face.verts)]
    assert interior
    interior_surface = surface_tree(interior)
    selected = set()
    for face in bm.faces:
        if face.material_index == slot and all(vertex.index in mapping for vertex in face.verts):
            projected_face = [mapping[vertex.index] for vertex in face.verts]
            x, y = np.mean(projected_face, axis=0)
            if ((x - 431.) / 47.)**2 + ((y - 539.) / 21.)**2 < 1. and min(point[1] for point in projected_face) >= 523.:
                selected.add(face)
    assert all(face in selected for edge in slit_edges for face in edge.link_faces)
    edge_set = {edge for face in selected for edge in face.edges
                if len(edge.link_faces) == 2 and any(neighbor not in selected for neighbor in edge.link_faces)}
    ring = ordered_ring(edge_set)
    boundary = np.array([mapping[vertex.index] for vertex in ring])
    x, y = boundary.T
    orientation = np.sum(x * np.roll(y, -1) - y * np.roll(x, -1))
    if orientation < 0:
        ring.reverse()
        boundary = boundary[::-1]
    old_indices = {vertex.index for face in selected for vertex in face.verts}
    head_group = head.vertex_groups['J_Bip_C_Head'].index
    weights = bm.verts.layers.deform.active
    kinds = {tuple((group, value) for group, value in bm.verts[i][weights].items() if value > 0.) for i in old_indices}
    assert kinds == {((head_group, 1.),)}, kinds
    design = np.c_[boundary, np.ones(len(boundary))]
    xz = np.array([(vertex.co.x, vertex.co.z) for vertex in ring])
    plane = np.linalg.lstsq(design, xz, rcond=None)[0]
    assert np.max(np.abs(design @ plane - xz)) < 1e-6
    layers = list(bm.loops.layers.uv.values())
    surrounding = [face for face in bm.faces if face not in selected]

    def surface_coordinates():
        return [(face.material_index, tuple((tuple(loop.vert.co), *(tuple(loop[layer].uv) for layer in layers))
                                           for loop in face.loops)) for face in surrounding]

    preserved = surface_coordinates()
    uv_equations={}
    boundary_uv={}
    for layer in layers:
        uv_coords=np.array([tuple(next(f for f in v.link_loops if f.face.material_index==slot)[layer].uv)
                            for v in ring])
        equation=np.linalg.lstsq(design,uv_coords,rcond=None)[0]
        if layer.name=='BaiQiCanvas':
            assert np.max(np.abs(design@equation-uv_coords))<1e-5
        uv_equations[layer.name]=equation
        boundary_uv[layer.name]=dict(zip(ring,uv_coords,strict=True))
    face_count=len(selected)
    bmesh.ops.delete(bm,geom=list(selected),context='FACES_ONLY')
    lose=[v for v in bm.verts if v.index in old_indices and not v.link_faces]
    bmesh.ops.delete(bm,geom=lose,context='VERTS')
    assert all(e.is_boundary for e in edge_set)
    reverse=np.roll(boundary,-1,axis=0)-boundary

    def depth(x,y):
        hit,_,_,_=surface.ray_cast(Vector((x,y,200.)),Vector((0.,0.,-1.)),410.)
        return hit.z if hit is not None else None

    def height(x,y):
        previous=depth(x,y)
        origins=[depth(x,v) for v in (522.,525.,554.,557.)]
        if any(v is None for v in origins):
            assert previous is not None
            return previous
        a,b,c,d=origins
        t=(y-522.)/35.
        # Match the depth and slope of both neighboring skin sections.
        wanted=((2*t**3-3*t*t+1)*a+(t**3-2*t*t+t)*(b-a)*35./3.
                +(-2*t**3+3*t*t)*d+(t**3-t*t)*(d-c)*35./3.)
        lane=smooth((x-410.)/14.)*smooth((468.-x)/15.)
        # The original closed-mouth artwork spans x=412–466 at y=533–535.
        line=534.1-.56*((x-439.)/27.)**2
        wanted+=lane*(lower_volume*np.exp(-.5*((y-line-3.0)/2.65)**2)
                      +upper_volume*np.exp(-.5*((y-line+2.)/2.2)**2)
                      -recess*np.exp(-.5*((y-line)/1.45)**2))
        q=np.array((x,y))-boundary
        along=np.clip(np.sum(q*reverse,axis=1)/np.sum(reverse*reverse,axis=1),0.,1.)
        distance=np.min(np.linalg.norm(q-along[:,None]*reverse,axis=1))
        fraction=smooth(distance/8.)
        fraction*=smooth((y-520.)/7.)*smooth((559.-y)/7.)
        return wanted if previous is None else previous+(wanted-previous)*fraction

    xy=[Vector(v) for v in boundary]
    for j,y in enumerate(np.r_[np.arange(523.5,530.,1.72),np.arange(530.2,540.,.93),np.arange(540.3,559.5,1.74)]):
        for x in np.arange(384.5+(j%2)*1.03,478.5,2.06):
            if np.min(np.linalg.norm(boundary-[x,y],axis=1))>.39:
                xy.append(Vector((x,y)))
    positions,_,triangles,ids,_,_=delaunay_2d_cdt(xy,[],[list(range(len(boundary)))],1,.00003)
    used={i for triangle in triangles for i in triangle}
    patch={}
    created=0
    for i in sorted(used):
        x,y=positions[i]
        names=ids[i]
        mark=[i for i in names if i<len(ring)]
        if mark:
            assert len(mark)==1
            vertex=ring[mark[0]]
        else:
            c=np.array((x,y,1.))@plane
            vertex=bm.verts.new((c[0],height(x,y)*.001,c[1]))
            vertex[weights][head_group] = 1.
            created+=1
        patch[i]=vertex
    replacement = []
    for triangle in triangles:
        face=bm.faces.new([patch[i] for i in triangle])
        replacement.append(face)
        face.material_index=slot
        face.smooth=True
        face.normal_update()
        if face.normal.y<0:
            face.normal_flip()
        assert face.normal.y>.1
        mapping_new={patch[i]:tuple(positions[i]) for i in triangle}
        for l in face.loops:
            x,y=mapping_new[l.vert]
            for layer in layers:
                old=boundary_uv[layer.name].get(l.vert)
                l[layer].uv=tuple(old if old is not None else np.array((x,y,1.))@uv_equations[layer.name])
    assert all(e.is_contiguous for e in edge_set)
    assert len(triangles) == 2 * created + len(edge_set) - 2
    assert all(vertex.link_faces for vertex in patch.values())
    assert surface_coordinates() == preserved
    interior_contacts = len(surface_tree(replacement).overlap(interior_surface))
    assert interior_contacts == 0
    bm.to_mesh(mesh)
    bm.free()
    return {'old_faces':face_count,'old_interior_vertices':len(lose),'new_faces':len(triangles),
            'new_vertices':created,'boundary_edges':len(edge_set),'old_lip_edges':len(slit),
            'mouth_depression_mm':recess,'lip_volume_scale':volume_scale,
            'lower_lip_profile_mm':lower_volume,'upper_lip_profile_mm':upper_volume,
            'mouth_interior_contact_pairs':interior_contacts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--lip-volume-scale', type=float, default=1.,
                        help='Scale the rounded outer lip profiles while holding the crease fixed.')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if not math.isfinite(args.lip_volume_scale) or args.lip_volume_scale < 0.:
        parser.error('--lip-volume-scale must be finite and nonnegative')
    source, inputs, output = ((ROOT / arg).resolve() for arg in (args.source, args.source_inputs, args.out))
    assert output != source and output.is_relative_to(ROOT)
    manifest = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    for form in ('coat_on', 'coat_off'):
        file = source / f'BaiQi_CC0_{form}.blend'
        initial = fingerprint(file)
        assert initial == manifest[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(file))
        head, body, arm = (bpy.data.objects[name] for name in (HEAD, 'Body', 'Armature'))
        before = mesh_fingerprint(head)
        fixed = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects
                 if obj.type == 'MESH' and obj != head}
        assert fixed[body] == manifest[form]['body_sha256']
        rest = rest_signature(arm)
        stats = refit_mouth(head, args.lip_volume_scale)
        assert all(mesh_fingerprint(obj) == sig for obj, sig in fixed.items())
        assert rest_signature(arm) == rest
        target = output / file.name
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        records[form] = {'source_sha256': initial, 'candidate_sha256': fingerprint(target),
                         'cc0_body_sha256': fixed[body], 'original_head_sha256': before,
                         'candidate_head_sha256': mesh_fingerprint(head), **stats}
    (output / 'mouth_design.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
