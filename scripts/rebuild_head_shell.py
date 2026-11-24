"""Unify folded generated head sheets and close real cut boundaries.

Voxel union removes duplicate internal surfaces. UVs are interpolated from
the original illustration projection after the geometry is made watertight.
"""
import argparse,json,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True)
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=(ROOT/args.output).resolve();assert out.is_relative_to(ROOT);out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/args.source))
mesh=next(o for o in bpy.data.objects if o.type=='MESH');head_index=mesh.vertex_groups['head'].index
bm=bmesh.new();bm.from_mesh(mesh.data);origin=bm.faces.layers.int['rebuild_origin'];deform=bm.verts.layers.deform.verify()
selected=[f for f in bm.faces if f[origin]==0 and min(v.co.z for v in f.verts)>1.58 and all(v[deform].get(head_index,0)>.999 for v in f.verts)]
assert len(selected)>1000,len(selected)
copy=bmesh.new();uv=copy.loops.layers.uv.new('Live2DFrontProjection');old_uv=bm.loops.layers.uv.active;mapping={};seen_faces=set();duplicates=0
for f in selected:
    key=frozenset(f.verts)
    if key in seen_faces:duplicates+=1;continue
    seen_faces.add(key)
    for v in f.verts:
        if v not in mapping:mapping[v]=copy.verts.new(v.co)
    q=copy.faces.new([mapping[v] for v in f.verts]);q.material_index=f.material_index;q.smooth=True
    for a,b in zip(q.loops,f.loops):a[uv].uv=b[old_uv].uv
bmesh.ops.triangulate(copy,faces=list(copy.faces));copy.verts.index_update();copy.faces.index_update()
coords=[v.co.copy() for v in copy.verts];faces=[[v.index for v in f.verts] for f in copy.faces]
uvs=[[Vector((*l[uv].uv,0)) for l in f.loops] for f in copy.faces];mats=[f.material_index for f in copy.faces]
tree=BVHTree.FromPolygons(coords,faces,all_triangles=True)
bmesh.ops.delete(bm,geom=selected,context='FACES');bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
bm.to_mesh(mesh.data);bm.free()
print('RETAINED_HEAD_FACES',sum(all(any(g.group==head_index and g.weight>.999 for g in mesh.data.vertices[i].groups) for i in f.vertices) for f in mesh.data.polygons),flush=True)
data=bpy.data.meshes.new('Closed head');copy.to_mesh(data);copy.free();obj=bpy.data.objects.new('Closed head',data);bpy.context.collection.objects.link(obj)
for mat in mesh.data.materials:data.materials.append(mat)
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
data.remesh_voxel_size=.002;data.remesh_voxel_adaptivity=0.;bpy.ops.object.voxel_remesh()
mod=obj.modifiers.new('Remove head sheet folds','SMOOTH');mod.factor=.35;mod.iterations=3;bpy.ops.object.modifier_apply(modifier=mod.name)
data=obj.data
print('HEAD_VOXEL_RESULT',len(data.vertices),len(data.polygons),flush=True)
obj.vertex_groups.clear();group=obj.vertex_groups.new(name='head');group.add(list(range(len(data.vertices))),1.,'REPLACE')
layer=data.uv_layers.get('Live2DFrontProjection') or data.uv_layers.new(name='Live2DFrontProjection')
for polygon in data.polygons:
    _,_,fi,_=tree.find_nearest(polygon.center);polygon.material_index=mats[fi];polygon.use_smooth=True
    for li in polygon.loop_indices:
        hit,_,fi,_=tree.find_nearest(data.vertices[data.loops[li].vertex_index].co)
        layer.data[li].uv=barycentric_transform(hit,*[coords[i] for i in faces[fi]],*uvs[fi]).xy
tag=data.attributes.get('rebuild_origin') or data.attributes.new('rebuild_origin','INT','FACE')
for item in tag.data:item.value=0
audit=bmesh.new();audit.from_mesh(data);open_edges=sum(e.is_boundary for e in audit.edges);audit.free();assert open_edges==0,open_edges
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);mesh.select_set(True);bpy.context.view_layer.objects.active=mesh;bpy.ops.object.join()
sys.path.insert(0,str(ROOT/'scripts'));from delta_surface_normals import soften_face_normals
soften_face_normals(mesh)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Delta_live2d.blend'))
report={'source':args.source,'head_voxel_m':.002,'head_open_edges':open_edges,'original_head_faces':len(selected),'duplicate_input_faces':duplicates,'status':'pending_render_review'}
(out/'head_rebuild.json').write_text(json.dumps(report,indent=2));print('HEAD_SHELL_REBUILT',json.dumps(report))
