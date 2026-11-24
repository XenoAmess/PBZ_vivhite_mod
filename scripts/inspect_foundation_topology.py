"""Inspect source material boundaries without changing the female foundation."""
import bpy,bmesh,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'output/live2d_delta/anatomy_foundation_002/Delta_adult.blend'))
o=next(o for o in bpy.data.objects if o.type=='MESH');bm=bmesh.new();bm.from_mesh(o.data)
tag=bm.faces.layers.int['anatomy_source_material'];rows=[]
for k in sorted({f[tag] for f in bm.faces}):
    faces=[f for f in bm.faces if f[tag]==k];vs={v for f in faces for v in f.verts}
    rows.append({'id':k,'faces':len(faces),'bounds':[[min(v.co[i] for v in vs),max(v.co[i] for v in vs)] for i in range(3)]})
boundary={e for e in bm.edges if e.is_boundary};loops=[]
while boundary:
    pending=[boundary.pop()];group=set(pending)
    while pending:
        e=pending.pop()
        for v in e.verts:
            for n in v.link_edges:
                if n in boundary:boundary.remove(n);pending.append(n);group.add(n)
    vs={v for e in group for v in e.verts};loops.append({'edges':len(group),'bounds':[[min(v.co[i] for v in vs),max(v.co[i] for v in vs)] for i in range(3)]})
(ROOT/'artifacts/foundation_topology.json').write_text(json.dumps({'materials':rows,'boundaries':loops},indent=2));print('FOUNDATION_TOPOLOGY',rows,loops)
