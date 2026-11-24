"""Measure source-image arm regions in a fitted mesh, without changing it."""
import bpy
import json
import sys
from pathlib import Path
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[1]
folder=Path(sys.argv[sys.argv.index('--candidate')+1])
bpy.ops.wm.open_mainfile(filepath=str(folder/'Delta_live2d.blend'))
mesh=next(o for o in bpy.data.objects if o.type=='MESH')
uv=mesh.data.uv_layers[0]
pixels={}
for loop in mesh.data.loops:
    u,v=uv.data[loop.index].uv
    pixels[loop.vertex_index]=(u*1400,(1-v)*2200)
names={g.index:g.name for g in mesh.vertex_groups}
result={}
for side,sign in [('l',1),('r',-1)]:
    for region,ylo,yhi,xlo in [('upperarm',760,860,155),('elbow',860,920,195),('forearm',965,1020,260),('hand',1050,1140,300)]:
        selected=[v for v in mesh.data.vertices if v.index in pixels and ylo<pixels[v.index][1]<yhi and sign*(pixels[v.index][0]-694.5)>xlo]
        totals=defaultdict(float);counts=defaultdict(int)
        for vertex in selected:
            for g in vertex.groups:
                totals[names[g.group]]+=g.weight
                if g.weight>.05:counts[names[g.group]]+=1
        result[region+'_'+side]={'vertices':len(selected),'mean_weights':dict(sorted(((n,w/max(1,len(selected))) for n,w in totals.items()),key=lambda p:-p[1])),
                               'vertices_with_over_5pct':dict(counts)}
path=folder/'arm_weight_inspection.json'
path.write_text(json.dumps(result,indent=2))
print('ARM_WEIGHT_INSPECTION',json.dumps(result))
