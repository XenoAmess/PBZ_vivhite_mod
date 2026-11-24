"""Verify native reference, active bindings and actual body motion before QA."""
import hashlib,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Quaternion,Vector
from qa.rig_binding import binding_reasons
ROOT=Path(__file__).resolve().parents[1]
def preflight(arm,body,out):
    rows=[{'object':o.name,'armature_modifiers':[{'target':m.object.name if m.object else None,'enabled':m.show_viewport and m.show_render,'preserve_volume':m.use_deform_preserve_volume} for m in o.modifiers if m.type=='ARMATURE']} for o in bpy.context.scene.objects if o.type=='MESH']
    report={'canonical_rig':arm.name,'bones':len(arm.data.bones),'scene_armatures':[o.name for o in bpy.context.scene.objects if o.type=='ARMATURE'],'meshes':rows}
    reasons=binding_reasons(report);reference=ROOT/'repro/native_inputs/repair_015/Delta_adult.blend'
    with bpy.data.libraries.load(str(reference),link=False) as (src,dst):dst.armatures=src.armatures
    refs=[r for r in dst.armatures if r and len(r.bones)==264];assert len(refs)==1
    ref=refs[0];delta=0.;parents_match=True
    for bone in arm.data.bones:
        old=ref.bones.get(bone.name)
        if old is None:reasons.append('native bone missing: '+bone.name);continue
        delta=max(delta,float(np.max(np.abs(np.array(bone.matrix_local)-np.array(old.matrix_local)))))
        parents_match &= (bone.parent.name if bone.parent else None)==(old.parent.name if old.parent else None)
    if delta>1e-5 or not parents_match:reasons.append('native reference matrix or parent changed')
    report['native_reference_sha256']=hashlib.sha256(reference.read_bytes()).hexdigest();report['native_matrix_max_error']=delta;report['native_parents_match']=parents_match
    for data in dst.armatures:bpy.data.armatures.remove(data)
    if not reasons:
        saved={b.name:b.matrix_basis.copy() for b in arm.pose.bones};old_action=arm.animation_data.action if arm.animation_data else None
        arm.animation_data_create();arm.animation_data.action=None
        for bone in arm.pose.bones:bone.matrix_basis.identity()
        def evaluated():
            bpy.context.view_layer.update();o=body.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=o.to_mesh();coords=np.array([body.matrix_world@v.co for v in mesh.vertices]);o.to_mesh_clear();return coords
        neutral=evaluated()
        for name,axis,angle in [('upperarm_l',(0,1,0),-.45),('head',(1,0,0),-.35)]:
            q=arm.data.bones[name].matrix_local.to_quaternion();bone=arm.pose.bones[name];bone.rotation_mode='QUATERNION';bone.rotation_quaternion=q.inverted()@Quaternion(Vector(axis),angle)@q
        moved=evaluated();report['body_probe_max_motion_cm']=float(np.linalg.norm(moved-neutral,axis=1).max())
        if report['body_probe_max_motion_cm']<1:reasons.append('body does not respond to posed native bones')
        for bone in arm.pose.bones:bone.matrix_basis=saved[bone.name]
        arm.animation_data.action=old_action;bpy.context.view_layer.update()
    report['status']='failed' if reasons else 'passed';report['reasons']=reasons
    (Path(out)/'rig_preflight.json').write_text(json.dumps(report,indent=2))
    assert not reasons,'Rig preflight failed: '+'; '.join(reasons)
    return report
