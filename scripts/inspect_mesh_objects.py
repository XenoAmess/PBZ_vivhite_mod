import bpy,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
file=sys.argv[sys.argv.index('--')+1];bpy.ops.wm.open_mainfile(filepath=str(ROOT/file))
print('MESH_OBJECTS',json.dumps([{'name':o.name,'type':o.type,'render':not o.hide_render,'vertices':len(o.data.vertices) if o.type=='MESH' else None,'linked':bool(o.users_collection),'modifiers':[(m.name,m.type) for m in o.modifiers]} for o in bpy.data.objects]))
mesh=next(o for o in bpy.data.objects if o.type=='MESH');print('TOTAL',len(mesh.data.polygons),len(mesh.vertex_groups))
from collections import Counter
print('MATERIALS',[(m.name,c) for i,c in Counter(p.material_index for p in mesh.data.polygons).items() for m in [mesh.data.materials[i]]])
print('TRANSFORM',list(mesh.matrix_world))
tag=mesh.data.attributes.get('rebuild_origin')
head_floor=170 if max(v.co.z for v in mesh.data.vertices)>10 else 1.7
print('HEAD_TAGS',Counter(tag.data[p.index].value if tag else -1 for p in mesh.data.polygons if p.center.z>head_floor))
import bmesh
bm=bmesh.new();bm.from_mesh(mesh.data);head=[f for f in bm.faces if f.calc_center_median().z>1.7 and f.calc_center_median().y<.02]
print('CUSTOM_NORMALS',mesh.data.has_custom_normals,'front_winding',Counter(1 if f.normal.y<0 else -1 for f in head))
keys=Counter(tuple(sorted(tuple(round(c,7) for c in v.co) for v in f.verts)) for f in bm.faces)
print('GEOMETRIC_DUPLICATE_FACES',sum(n-1 for n in keys.values() if n>1))
