"""Repair discontinuous skin fields across fused neck/shoulder surfaces.

Geometry, UVs, normals and native rest transforms remain unchanged. The
generated union's neighboring vertices must not inherit unrelated donor fields
just because they lie on opposite sides of a construction-surface boundary.
"""
import argparse, hashlib, json, sys
from pathlib import Path
import bpy, numpy as np
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--source',default='output/live2d_delta/shoulder_rebuild/Delta_live2d.blend')
parser.add_argument('--output',default='output/live2d_delta/qa_repair_001/Delta_live2d.blend')
parser.add_argument('--iterations',type=int,default=160)
parser.add_argument('--neck-floor',type=float,default=1.525)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
source=(ROOT/args.source).resolve();output=(ROOT/args.output).resolve();assert output.is_relative_to(ROOT) and output!=source
output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(source))
mesh=next(o for o in bpy.data.objects if o.type=='MESH')
coords=np.array([v.co[:] for v in mesh.data.vertices]);geometry_hash=hashlib.sha256(coords.tobytes()).hexdigest()
n=len(coords);generated=np.zeros(n,dtype=bool);tag=mesh.data.attributes['rebuild_origin']
for p,item in zip(mesh.data.polygons,tag.data):
    if item.value==1:generated[list(p.vertices)]=True
x,y,z=coords.T
def smooth(t):t=np.clip(t,0,1);return t*t*(3-2*t)
neck=smooth((z-args.neck_floor)/.025)*smooth((1.68-z)/.035)*smooth((.095-abs(x))/.025)
shoulder=smooth((abs(x)-.08)/.045)*smooth((.34-abs(x))/.055)*smooth((z-1.35)/.065)*smooth((1.64-z)/.045)
mask=np.maximum(neck,shoulder)*generated
mask[(y<-.01)&(z>1.635)]=0 # keep the visible jaw attached rigidly to the head
selected=np.where(mask>.001)[0]
group_ids=sorted({g.group for i in selected for g in mesh.data.vertices[i].groups})
w=np.zeros((n,len(group_ids)),dtype=np.float64);lookup={g:i for i,g in enumerate(group_ids)}
for v in mesh.data.vertices:
    for item in v.groups:
        if item.group in lookup:w[v.index,lookup[item.group]]=item.weight
edges=np.array([e.vertices[:] for e in mesh.data.edges]);a=np.r_[edges[:,0],edges[:,1]];b=np.r_[edges[:,1],edges[:,0]]
length=np.linalg.norm(coords[a]-coords[b],axis=1)
edge_weight=1/np.maximum(length,.001)
degree=np.bincount(a,weights=edge_weight,minlength=n);degree=np.maximum(degree,1e-12)
before=w.copy()
for iteration in range(args.iterations):
    avg=np.column_stack([np.bincount(a,weights=edge_weight*w[b,j],minlength=n)/degree for j in range(w.shape[1])])
    w+=.62*mask[:,None]*(avg-w)
    if iteration%40==0:print('SKIN_FIELD_DIFFUSION',iteration,flush=True)
w[selected]/=w[selected].sum(axis=1,keepdims=True)
for group_id in group_ids:mesh.vertex_groups[group_id].remove(selected.tolist())
for i in selected:
    for j,value in enumerate(w[i]):
        if value>1e-7:mesh.vertex_groups[group_ids[j]].add([int(i)],float(value),'REPLACE')
sums=[sum(g.weight for g in mesh.data.vertices[int(i)].groups) for i in selected]
assert min(sums)>.99999 and max(sums)<1.00001
assert hashlib.sha256(np.array([v.co[:] for v in mesh.data.vertices]).tobytes()).hexdigest()==geometry_hash
local_edges=(mask[edges[:,0]]>.1)&(mask[edges[:,1]]>.1)
def delta(values):return np.sum(abs(values[edges[local_edges,0]]-values[edges[local_edges,1]]),axis=1)
report={'source':str(source.relative_to(ROOT)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'method':'edge-weighted Jacobi diffusion of skin weights with spatial boundary constraints',
    'iterations':args.iterations,'neck_floor_m':args.neck_floor,'changed_vertices':len(selected),'geometry_unchanged':True,
    'adjacent_weight_L1_before_p95_max':np.percentile(delta(before),[95,100]).tolist(),
    'adjacent_weight_L1_after_p95_max':np.percentile(delta(w),[95,100]).tolist(),
    'status':'requires_identical_ROM_rerender_and_visual_review'}
bpy.ops.wm.save_as_mainfile(filepath=str(output))
(output.parent/'repair_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('SKIN_FIELD_REPAIRED',json.dumps(report),flush=True)
