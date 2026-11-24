"""Independently reimport FBX and GLB, checking retained bones and deformation.
Run under Blender with --python-exit-code 1.
"""
import json
import sys
from pathlib import Path
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/live2d_delta/prototype'
if '--candidate' in sys.argv:OUT=Path(sys.argv[sys.argv.index('--candidate')+1]).resolve()
reference_path=next((ROOT/'artifacts/extracted').rglob('Hun_Body_Simple.Hun_Body_Simple.skel.json'))
reference=json.loads(reference_path.read_text())['bones']
expected={b['name']:(reference[b['parent']]['name'] if b['parent']>=0 else None) for b in reference}
report={'status':'offline_prototype_checks_only','game_runtime_tested':False,'formats':{}}
for extension in ['blend','glb','fbx']:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if extension=='blend': bpy.ops.wm.open_mainfile(filepath=str(OUT/'Delta_live2d.blend'))
    elif extension=='glb': bpy.ops.import_scene.gltf(filepath=str(OUT/'Delta_live2d.glb'),bone_heuristic='TEMPERANCE')
    else: bpy.ops.import_scene.fbx(filepath=str(OUT/'Delta_live2d.fbx'),use_anim=False)
    armatures=[o for o in bpy.data.objects if o.type=='ARMATURE']
    assert len(armatures)==1,(extension,'unexpected armatures')
    arm=armatures[0]
    actual={b.name:(b.parent.name if b.parent else None) for b in arm.data.bones}
    assert actual==expected,(extension,'bone names or parent graph changed')
    meshes=[o for o in bpy.data.objects if o.type=='MESH']
    assert len(meshes)==1,(extension,'unexpected meshes')
    mesh=meshes[0]
    sums=[sum(g.weight for g in v.groups) for v in mesh.data.vertices]
    assert all(abs(s-1)<1e-4 for s in sums),(extension,'missing or non-normalized weights')
    assert all(np.isfinite(v.co[:]).all() for v in mesh.data.vertices),(extension,'non-finite vertex')
    before=np.array([v.co[:] for v in mesh.data.vertices])
    arm.pose.bones['lowerarm_l'].rotation_mode='XYZ'
    arm.pose.bones['lowerarm_l'].rotation_euler[2]=.6
    bpy.context.view_layer.update()
    evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    posed=evaluated.to_mesh()
    after=np.array([v.co[:] for v in posed.vertices])
    assert np.isfinite(after).all(),(extension,'invalid posed vertices')
    moved=int((np.linalg.norm(after-before,axis=1)>1e-5).sum())
    assert moved>10,(extension,'arm pose does not deform mesh')
    evaluated.to_mesh_clear()
    report['formats'][extension]={'bones':len(actual),'parent_graph_matches_local_game':True,
        'vertices':len(mesh.data.vertices),'weight_sum_min':min(sums),'weight_sum_max':max(sums),
        'vertices_moved_by_arm_pose':moved}
report['limits']=['Tests establish data retention and finite deformation only',
                  'They do not establish visual quality, exact cooked bind transforms or in-game compatibility']
(OUT/'offline_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('OFFLINE_PROTOTYPE_VERIFIED',json.dumps(report))
