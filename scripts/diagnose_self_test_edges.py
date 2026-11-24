"""Locate deformed edges and expose their actual neighboring skin weights."""
import json
from pathlib import Path
import bpy, numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/live2d_delta/self_test'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Delta_SelfTest.blend'))
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');mesh=next(o for o in bpy.data.objects if o.type=='MESH')
arm.animation_data.action=None
for b in arm.pose.bones:b.matrix_basis.identity()
bpy.context.view_layer.update()
rest=np.array([(mesh.matrix_world@v.co)[:] for v in mesh.data.vertices])
edges=np.array([e.vertices[:] for e in mesh.data.edges]);lens=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1)
masks={'neck':(abs(rest[:,0])<5.5)&(rest[:,2]>157)&(rest[:,2]<166)&(rest[:,1]>-.5)&(rest[:,1]<10),
       'shoulder':(abs(rest[:,0])>12)&(abs(rest[:,0])<27)&(rest[:,2]>144)&(rest[:,2]<157)}
report=[]
for key,region in [('neck_pitch','neck'),('head_pivot','neck'),('arms_abduction','shoulder')]:
    arm.animation_data.action=bpy.data.actions['DeltaTest_'+key];bpy.context.scene.frame_set(77);bpy.context.view_layer.update()
    obj=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());data=obj.to_mesh()
    posed=np.array([(mesh.matrix_world@v.co)[:] for v in data.vertices]);obj.to_mesh_clear()
    mask=masks[region];ids=np.where(mask[edges[:,0]]&mask[edges[:,1]]&(lens>.03))[0]
    ratios=np.linalg.norm(posed[edges[ids,0]]-posed[edges[ids,1]],axis=1)/lens[ids]
    rows=[]
    for i in ids[np.argsort(ratios)[-5:][::-1]]:
        a,b=map(int,edges[i]);weights=[]
        for vi in [a,b]:weights.append({mesh.vertex_groups[g.group].name:float(g.weight) for g in mesh.data.vertices[vi].groups if g.weight>.0001})
        rows.append({'vertices':[a,b],'reference_length_cm':float(lens[i]),
            'posed_length_cm':float(np.linalg.norm(posed[a]-posed[b])),
            'rest_positions_cm':[rest[a].tolist(),rest[b].tolist()],'weights':weights,
            'weight_difference_L1':sum(abs(weights[0].get(n,0)-weights[1].get(n,0)) for n in set(weights[0])|set(weights[1]))})
    report.append({'clip':key,'frame':77,'region':region,'worst_edges':rows})
(OUT/'edge_diagnosis.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps([{'clip':r['clip'],'worst':r['worst_edges'][0]} for r in report]))
