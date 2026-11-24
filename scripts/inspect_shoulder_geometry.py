"""Measure the current garment against the native shoulder/arm joints."""
import json
from pathlib import Path
import bpy
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'output/live2d_delta/hunyuan21_polished/Delta_live2d.blend'))
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
mesh=next(o for o in bpy.data.objects if o.type=='MESH')
positions=np.array([(mesh.matrix_world@v.co)[:] for v in mesh.data.vertices])
uv=np.zeros((len(positions),2))
for loop in mesh.data.loops:uv[loop.vertex_index]=mesh.data.uv_layers.active.data[loop.index].uv[:]
pixel=np.c_[uv[:,0]*1400,(1-uv[:,1])*2200]
report={'joints':{},'sections':{}}
report['neck_head_joints']={name:list(arm.matrix_world@arm.data.bones[name].head_local) for name in ['spine_05','neck_01','neck_02','head']}
report['neck_source_slices']={}
report['torso_height_mapping']={}
for yy in range(700,1101,25):
    chosen=(abs(pixel[:,1]-yy)<8)&(abs(pixel[:,0]-694.5)<45)
    if chosen.any():report['torso_height_mapping'][yy]=np.median(positions[chosen],axis=0).tolist()
for yy in [540,580,600,620,640,660,680,700,720,740]:
    selected=(abs(pixel[:,1]-yy)<7)&(abs(pixel[:,0]-694.5)<140)
    if selected.any():report['neck_source_slices'][str(yy)]={'min':positions[selected].min(axis=0).tolist(),'max':positions[selected].max(axis=0).tolist()}
ownership=np.load(ROOT/'artifacts/live2d/arm_ownership.npy')
px=np.clip(np.rint(pixel[:,0]).astype(int),0,1399);py=np.clip(np.rint(pixel[:,1]).astype(int),0,2199)
own=ownership[py,px]
report['arm_source_slices']={}
for side,sign in [('l',1),('r',-1)]:
    p={name:np.array((arm.matrix_world@arm.data.bones[name+'_'+side].head_local)[:]) for name in ['clavicle','upperarm','lowerarm','hand']}
    report['joints'][side]={name:value.tolist() for name,value in p.items()}
    report['sections'][side]={}
    report['arm_source_slices'][side]={}
    for yy in [710,735,760,785,810,835,860,885,910,935,960,985,1010]:
        select=(abs(pixel[:,1]-yy)<8)&(sign*(pixel[:,0]-694.5)>70)&(own>.8)
        if select.any():report['arm_source_slices'][side][str(yy)]={'n':int(select.sum()),'center':positions[select].mean(axis=0).tolist(),'bounds':[positions[select].min(axis=0).tolist(),positions[select].max(axis=0).tolist()]}
    for segment,(start,end) in enumerate([('upperarm','lowerarm'),('lowerarm','hand')]):
        a,b=p[start],p[end];axis=b-a;length=np.linalg.norm(axis);axis/=length
        t=(positions-a)@axis
        radial=positions-a-t[:,None]*axis
        radius=np.linalg.norm(radial,axis=1)
        for fraction in [0.,.15,.35,.5,.75,1.]:
            selected=(abs(t-length*fraction)<.008)&(radius<.15)&(sign*positions[:,0]>.12)&(own>.8)
            if not selected.any():continue
            report['sections'][side][start+':'+str(fraction)]={'n':int(selected.sum()),
                'centroid_offset_m':np.mean(radial[selected],axis=0).tolist(),
                'radius_m_p10_50_90':np.percentile(radius[selected],[10,50,90]).tolist(),
                'source_pixels_min':pixel[selected].min(axis=0).tolist(),'source_pixels_max':pixel[selected].max(axis=0).tolist()}
(ROOT/'artifacts/shoulder_geometry_v02.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
