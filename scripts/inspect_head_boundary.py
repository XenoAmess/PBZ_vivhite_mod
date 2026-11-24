"""Report the retained head's open loops, without changing any input."""
import json
from pathlib import Path
import bpy,bmesh
ROOT=Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'output/live2d_delta/qa_geometry_007/Delta_live2d.blend'))
obj=next(o for o in bpy.data.objects if o.type=='MESH')
bm=bmesh.new();bm.from_mesh(obj.data);uv=bm.loops.layers.uv.active
boundary={e for e in bm.edges if e.is_boundary and min(v.co.z for v in e.verts)>1.58}
loops=[]
while boundary:
    first=boundary.pop();seen={first};stack=[first]
    while stack:
        e=stack.pop()
        for v in e.verts:
            for q in v.link_edges:
                if q in boundary:boundary.remove(q);seen.add(q);stack.append(q)
    verts=set(v for e in seen for v in e.verts)
    loops.append({'edges':len(seen),'verts':[list(v.co) for v in verts],
        'uv_y_range':[min((1-l[uv].uv.y)*2200 for v in verts for l in v.link_loops),max((1-l[uv].uv.y)*2200 for v in verts for l in v.link_loops)]})
(ROOT/'artifacts/head_boundaries.json').write_text(json.dumps(loops,indent=2))
print('HEAD_BOUNDARIES',[(q['edges'],q['uv_y_range']) for q in loops])
