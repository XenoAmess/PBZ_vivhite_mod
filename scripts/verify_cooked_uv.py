import json
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools/blender_libs'),str(ROOT/'vendor/UEFormat/plugins/blender')]
from io_scene_ueformat.importer.import_context import UEFormatImport
from io_scene_ueformat.options import UEModelOptions
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'build/model_inputs/Delta_adult.blend'))
expected=next(o for o in bpy.data.objects if o.type=='MESH')
before=set(bpy.data.objects)
path=next((ROOT/'artifacts/extracted/candidate_readback').rglob('Hun_Body_Simple.uemodel'))
UEFormatImport(UEModelOptions(scale_factor=1.,reorient_bones=False,import_sockets=False,import_morph_targets=False)).import_file(path)
actual=next(o for o in bpy.data.objects if o not in before and o.type=='MESH')
def uv_by_vertex(mesh,index):
    result=np.zeros((len(mesh.data.vertices),2))
    for loop in mesh.data.loops:result[loop.vertex_index]=mesh.data.uv_layers[index].data[loop.index].uv[:]
    return result
tree=KDTree(len(expected.data.vertices))
for v in expected.data.vertices:tree.insert(expected.matrix_world@v.co,v.index)
tree.balance()
indices=np.array([tree.find(actual.matrix_world@v.co)[1] for v in actual.data.vertices])
front=np.zeros(len(actual.data.vertices),dtype=bool)
for p in actual.data.polygons:
    if p.material_index==10:
        for v in p.vertices:front[v]=True
rows=[]
for i,layer in enumerate(expected.data.uv_layers):
    source=uv_by_vertex(expected,i)[indices]
    for j,target_layer in enumerate(actual.data.uv_layers):
        target=uv_by_vertex(actual,j)
        direct=np.linalg.norm(target-source,axis=1)
        flipped=source.copy();flipped[:,1]=1-flipped[:,1]
        reverse=np.linalg.norm(target-flipped,axis=1)
        rows.append({'source_uv':layer.name,'cooked_uv':target_layer.name,
                     'source_active_render':layer.active_render,
                     'direct_p99':float(np.percentile(direct[front],99)),
                     'flipped_v_p99':float(np.percentile(reverse[front],99)),
                     'samples':list(zip(source[front][:3].tolist(),target[front][:3].tolist()))})
face_forward=[]
for polygon in actual.data.polygons:
    if polygon.material_index!=10:continue
    for index in polygon.loop_indices:
        u,v=actual.data.uv_layers[0].data[index].uv
        radius=((u*1400-694.5)**2/88**2+((1-v)*2200-550)**2/66**2)**.5
        if radius<.5:face_forward.append(-actual.data.corner_normals[index].vector.y)
assert len(face_forward)>20,'Face normal sample missing'
face_normals={'corners':len(face_forward),'forward_cosine_p10':float(np.percentile(face_forward,10)),
              'forward_cosine_median':float(np.median(face_forward))}
assert face_normals['forward_cosine_p10']>.95,('Face smoothing normals were lost',face_normals)
assert min(r['direct_p99'] for r in rows)<.001,'Projection UV mismatch'
report={'uv_comparison':rows,'smoothed_face_normals':face_normals}
(ROOT/'artifacts/cooked_uv_comparison.json').write_text(json.dumps(report,indent=2))
print('COOKED_UV_COMPARISON',json.dumps(report))
