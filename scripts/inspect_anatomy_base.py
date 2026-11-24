"""Inspect the CC0 reference base before any geometry is adopted."""
import json
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'artifacts/anatomy_base/Base_Female.glb'))
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
report={'objects':[{'name':o.name,'type':o.type,'vertices':len(o.data.vertices) if o.type=='MESH' else None,'materials':[m.name for m in o.data.materials] if o.type=='MESH' else None} for o in bpy.data.objects],
    'bones':[{'name':b.name,'head':list(arm.matrix_world@b.head_local),'tail':list(arm.matrix_world@b.tail_local)} for b in arm.data.bones]}
import numpy as np
report['material_landmarks']=[]
for obj in [o for o in bpy.data.objects if o.type=='MESH' and o.data.materials]:
    for i,mat in enumerate(obj.data.materials):
        ids=set(v for p in obj.data.polygons if p.material_index==i for v in p.vertices)
        if not ids:continue
        coords=np.array([obj.matrix_world@obj.data.vertices[v].co for v in ids])
        report['material_landmarks'].append({'object':obj.name,'material':mat.name,'min_m':coords.min(axis=0).tolist(),'max_m':coords.max(axis=0).tolist(),
            'left_mean_m':coords[coords[:,0]<0].mean(axis=0).tolist() if (coords[:,0]<0).any() else None,'right_mean_m':coords[coords[:,0]>0].mean(axis=0).tolist() if (coords[:,0]>0).any() else None})
(ROOT/'artifacts/anatomy_base/import_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'artifacts/anatomy_base/Base_Female.blend'));print('ANATOMY_REFERENCE_IMPORTED',len(arm.data.bones))
