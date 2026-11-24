"""Compare cooked geometry and real game poses with the selected Blender input."""
import json
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils.kdtree import KDTree

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools/blender_libs'),str(ROOT/'vendor/UEFormat/plugins/blender')]
from io_scene_ueformat.importer.import_context import UEFormatImport
from io_scene_ueformat.options import UEModelOptions,UEAnimOptions

bpy.ops.wm.open_mainfile(filepath=str(ROOT/'build/model_inputs/Delta_adult.blend'))
original_arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
expected=next(o for o in bpy.data.objects if o.type=='MESH')
before=set(bpy.data.objects)
path=next((ROOT/'artifacts/extracted/candidate_readback').rglob('Hun_Body_Simple.uemodel'))
UEFormatImport(UEModelOptions(scale_factor=1.,reorient_bones=False,import_sockets=False,import_morph_targets=False)).import_file(path)
imported=[o for o in bpy.data.objects if o not in before]
arm=next(o for o in imported if o.type=='ARMATURE')
actual=next(o for o in imported if o.type=='MESH')
weights_summary={}
for obj in [expected,actual]:
    sums=[sum(g.weight for g in v.groups) for v in obj.data.vertices]
    weights_summary[obj.name]={'min_sum':min(sums),'max_sum':max(sums),
                              'maximum_influences':max(len(v.groups) for v in obj.data.vertices),
                              'max_distance_from_8bit_step':max(abs(g.weight*255-round(g.weight*255)) for v in obj.data.vertices for g in v.groups)}
assert len(arm.data.bones)==264
for bone in original_arm.data.bones:
    a=original_arm.matrix_world@bone.matrix_local
    b=arm.matrix_world@arm.data.bones[bone.name].matrix_local
    assert (a.translation-b.translation).length<.002,('Cooked bone head mismatch',bone.name)
    assert abs(a.to_quaternion().dot(b.to_quaternion()))>.99999,('Cooked bone axis mismatch',bone.name)
expected.parent=arm
for modifier in expected.modifiers:
    if modifier.type=='ARMATURE':modifier.object=arm
bpy.data.objects.remove(original_arm,do_unlink=True)
def positions(obj):
    bpy.context.view_layer.update();evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data=evaluated.to_mesh()
    values=np.array([(obj.matrix_world@v.co)[:] for v in data.vertices])
    evaluated.to_mesh_clear();return values
def compare(name):
    a=positions(expected);b=positions(actual)
    assert np.isfinite(a).all() and np.isfinite(b).all()
    tree=KDTree(len(a))
    for index,p in enumerate(a):tree.insert(p,index)
    tree.balance()
    distances=np.array([tree.find(p)[2] for p in b])
    row={'pose':name,'expected_vertices':len(a),'cooked_vertices':len(b),
         'nearest_position_error_cm_p99':float(np.percentile(distances,99)),
         'nearest_position_error_cm_max':float(distances.max())}
    if '--diagnostic' not in sys.argv:
        assert row['nearest_position_error_cm_p99']<.25,row
        assert row['nearest_position_error_cm_max']<1.0,row
    return row
report={'status':'diagnostic_only' if '--diagnostic' in sys.argv else 'cooked_geometry_and_pose_check',
        'runtime_tested':False,'weight_sums':weights_summary,'samples':[compare('reference')]}
for name,frame in [('Hun_Unarmed_Idle_Loop',77),('Hun_Unarmed_Run_Fwd_Loop',25),('Hun_BaiShanDual_Attack_A',33),('Hun_BaiShanDual_Attack_A',66),('Hun_BaiShanDual_Attack_A',99)]:
    clip=next((ROOT/'artifacts/extracted/arm_audit').rglob(name+'.ueanim'))
    UEFormatImport(UEAnimOptions(scale_factor=1.,override_skeleton=arm,import_curves=False)).import_file(clip)
    bpy.context.scene.frame_set(frame)
    report['samples'].append(compare(name+':'+str(frame)))
report['limits']=['Nearest surface comparison after format conversion; not a topology identity check',
                  'Does not include live game AnimBP, IK, weapon attachment or cloth simulation']
report['container_files']=json.loads((ROOT/'output/live2d_delta/game_candidate/manifest.json').read_text())['files']
out=ROOT/'output/live2d_delta/game_candidate/cooked_deformation.json'
out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print('COOKED_DEFORMATION_VERIFIED',json.dumps(report))
