"""Scan complete native clips and locate geometric strain, without rendering."""
import json
import sys
from pathlib import Path
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
candidate=Path(sys.argv[sys.argv.index('--candidate')+1]) if '--candidate' in sys.argv else ROOT/'build/model_inputs/Delta_adult.blend'
out=Path(sys.argv[sys.argv.index('--output')+1]) if '--output' in sys.argv else ROOT/'artifacts/arm_hotspots.json'
sys.path[:0]=[str(ROOT/'tools/blender_libs'),str(ROOT/'vendor/UEFormat/plugins/blender')]
from io_scene_ueformat.importer.import_context import UEFormatImport
from io_scene_ueformat.options import UEAnimOptions,UEModelOptions
if '--original' in sys.argv:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path=ROOT/'artifacts/extracted/original/HuaShira/Characters/Hero/Hero_Hun/SkinParts/Hun_Body_Simple.uemodel'
    UEFormatImport(UEModelOptions(scale_factor=1.,reorient_bones=False,import_sockets=False,import_morph_targets=False)).import_file(path)
else:bpy.ops.wm.open_mainfile(filepath=str(candidate))
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
mesh=next(o for o in bpy.data.objects if o.type=='MESH')
names={g.index:g.name for g in mesh.vertex_groups}
edges=np.array([e.vertices[:] for e in mesh.data.edges])
rest=np.empty(len(mesh.data.vertices)*3,dtype=np.float32);mesh.data.vertices.foreach_get('co',rest);rest=rest.reshape(-1,3)
lengths=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1)
regions={}
for region,words in [('arms',['upperarm','lowerarm','hand','thumb','index','middle','ring','pinky','wrist']),
                     ('upperarms',['upperarm']),('forearms',['lowerarm']),('hands',['hand','thumb','index','middle','ring','pinky','wrist'])]:
    vertex_mask=np.array([sum(g.weight for g in v.groups if any(k in names[g.group] for k in words))>.65 for v in mesh.data.vertices])
    regions[region]=vertex_mask[edges[:,0]]&vertex_mask[edges[:,1]]&(lengths>.02)
pixels=np.zeros((len(rest),2))
uv=mesh.data.uv_layers[0]
for loop in mesh.data.loops:
    u,v=uv.data[loop.index].uv;pixels[loop.vertex_index]=(u*1400,(1-v)*2200)
report={'candidate':str(candidate),'clips':{},'runtime_tested':False}
clips=list((ROOT/'artifacts/extracted/arm_audit').rglob('*.ueanim'))
if '--clips' in sys.argv:clips+=list(Path(sys.argv[sys.argv.index('--clips')+1]).rglob('*.ueanim'))
for path in clips:
    action,dto=UEFormatImport(UEAnimOptions(scale_factor=1.,override_skeleton=arm,import_curves=False)).import_file_with_dto(path)
    if int(dto.metadata.additive_anim_type)!=0:continue
    record={'frames':dto.metadata.num_frames,'worst':{},'hotspots':[]}
    top=[]
    for frame in range(dto.metadata.num_frames):
        bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
        evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());geometry=evaluated.to_mesh()
        posed=np.empty(len(rest)*3,dtype=np.float32);geometry.vertices.foreach_get('co',posed);posed=posed.reshape(-1,3)
        evaluated.to_mesh_clear();assert np.isfinite(posed).all()
        ratios=np.linalg.norm(posed[edges[:,0]]-posed[edges[:,1]],axis=1)/np.maximum(lengths,1e-8)
        for name,mask in regions.items():
            values=ratios[mask]
            metric={'frame':frame,'p99':float(np.percentile(values,99)),'max':float(values.max()),'edges_over_2x':int((values>2).sum())}
            if name not in record['worst'] or metric['p99']>record['worst'][name]['p99']:record['worst'][name]=metric
        indices=np.where(regions['arms'])[0]
        worst=indices[np.argsort(ratios[indices])[-6:]]
        for index in worst:top.append((float(ratios[index]),frame,int(index)))
    seen=set()
    for ratio,frame,index in sorted(top,reverse=True):
        if index in seen:continue
        seen.add(index);a,b=edges[index]
        record['hotspots'].append({'ratio':ratio,'frame':frame,'edge':int(index),'rest_length_cm':float(lengths[index]),
                                  'pixel':((pixels[a]+pixels[b])/2).tolist(),'position_cm':((rest[a]+rest[b])/2).tolist(),
                                  'weights':[{names[g.group]:g.weight for g in mesh.data.vertices[int(v)].groups} for v in [a,b]]})
        if len(seen)==12:break
    report['clips'][path.stem]=record
    print('FULL_CLIP_SCANNED',path.stem,record['frames'],json.dumps(record['worst']),flush=True)
out.write_text(json.dumps(report,indent=2),encoding='utf-8')
