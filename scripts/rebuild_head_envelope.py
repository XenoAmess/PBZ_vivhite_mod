"""Build one solid head envelope from front/back ray depths.

Unlike voxelizing folded open sheets, this explicitly has one outer front,
one outer back, and stitched silhouette walls. Internal duplicate sheets
cannot survive. Original front illustration coordinates remain unchanged.
"""
import argparse,json,sys
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True)
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=(ROOT/args.output).resolve();assert out.is_relative_to(ROOT);out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/args.source));mesh=next(o for o in bpy.data.objects if o.type=='MESH');head_index=mesh.vertex_groups['head'].index
bm=bmesh.new();bm.from_mesh(mesh.data);origin=bm.faces.layers.int['rebuild_origin'];deform=bm.verts.layers.deform.verify()
selected=[f for f in bm.faces if f[origin]==0 and min(v.co.z for v in f.verts)>1.58 and all(v[deform].get(head_index,0)>.999 for v in f.verts)]
assert len(selected)>1000
vertices=list(set(v for f in selected for v in f.verts));index={v:i for i,v in enumerate(vertices)}
tree=BVHTree.FromPolygons([v.co for v in vertices],[[index[v] for v in f.verts] for f in selected])
points=np.array([v.co[:] for v in vertices]);step=.002
xs=np.arange(np.floor(points[:,0].min()/step)*step,np.ceil(points[:,0].max()/step)*step+step/2,step)
zs=np.arange(np.floor(points[:,2].min()/step)*step,np.ceil(points[:,2].max()/step)*step+step/2,step)
depths={}
def jaw_height(x):return 1.645+.045*min(1,abs(x)/.075)**1.8
def smooth(t):t=max(0,min(1,t));return t*t*(3-2*t)
for i,x in enumerate(xs):
    for j,z in enumerate(zs):
        front=tree.ray_cast(Vector((x,-.8,z)),Vector((0,1,0)))[0]
        back=tree.ray_cast(Vector((x,.8,z)),Vector((0,-1,0)))[0]
        if front is not None and back is not None:
            fy=float(front.y)
            if abs(x)<.075:
                t=smooth((jaw_height(x)-z)/.012)*smooth((.075-abs(x))/.015)
                fy=fy*(1-t)+.095*t
            depths[i,j]=(fy,max(float(back.y),fy+.003))
g=bmesh.new();uv=g.loops.layers.uv.new('Live2DFrontProjection');dv=g.verts.layers.deform.verify();pairs={}
for (i,j),(front,back) in depths.items():
    pairs[i,j]=[g.verts.new((float(xs[i]),y,float(zs[j]))) for y in [front,back]]
    for v in pairs[i,j]:v[dv][head_index]=1.
def face(vs,material):
    f=g.faces.new(vs);f.material_index=material;f.smooth=True
    for l in f.loops:
        x,y,z=l.vert.co
        py=592-(z-1.649674)/(1.95/1607)
        if material==1:py=min(py,590)
        l[uv].uv=(.99,.01) if material==6 else ((694.5+x/(1.95/1607))/1400,1-py/2200)
    return f
front_faces=[]
for i,j in list(pairs):
    keys=[(i,j),(i+1,j),(i+1,j+1),(i,j+1)]
    if all(k in pairs for k in keys):
        x=(xs[i]+xs[i+1])*.5;z=(zs[j]+zs[j+1])*.5
        material=(6 if z>jaw_height(x)-.006 else 1) if z<jaw_height(x)+.010 and abs(x)<.075 else (1 if z<1.666 else 0)
        front_faces.append(face([pairs[k][0] for k in keys],material))
        face([pairs[k][1] for k in reversed(keys)],1)
front_to_back={a:b for a,b in pairs.values()}
silhouette=[e for e in g.edges if e.is_boundary and all(v in front_to_back for v in e.verts)]
for e in silhouette:
    a,b=e.verts;center=(a.co+b.co)/2
    face([b,a,front_to_back[a],front_to_back[b]],6 if abs(center.x)<.052 and center.y<.065 and center.z<1.67 else 1)
bmesh.ops.delete(g,geom=[v for v in g.verts if not v.link_faces],context='VERTS')
bmesh.ops.recalc_face_normals(g,faces=list(g.faces))
open_edges=sum(e.is_boundary for e in g.edges);assert open_edges==0,open_edges
bmesh.ops.delete(bm,geom=selected,context='FACES');bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS');bm.to_mesh(mesh.data);bm.free()
data=bpy.data.meshes.new('Solid head envelope');g.to_mesh(data);g.free();obj=bpy.data.objects.new('Solid head envelope',data);bpy.context.collection.objects.link(obj)
for m in mesh.data.materials:data.materials.append(m)
for group in mesh.vertex_groups:obj.vertex_groups.new(name=group.name)
tag=data.attributes.new('rebuild_origin','INT','FACE')
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
mod=obj.modifiers.new('Smooth depth sampling','SMOOTH');mod.factor=.3;mod.iterations=3;bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);mesh.select_set(True);bpy.context.view_layer.objects.active=mesh;bpy.ops.object.join()
sys.path.insert(0,str(ROOT/'scripts'));from delta_surface_normals import soften_face_normals
soften_face_normals(mesh);bpy.ops.wm.save_as_mainfile(filepath=str(out/'Delta_live2d.blend'))
report={'source':args.source,'method':'single front/back depth envelope with stitched silhouette','sampling_step_m':step,'head_open_edges':open_edges,'status':'pending_render_review'}
(out/'head_rebuild.json').write_text(json.dumps(report,indent=2));print('HEAD_ENVELOPE_READY',json.dumps(report))
