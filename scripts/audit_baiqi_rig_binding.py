"""Inspect and optionally repair mesh bindings without changing native bones."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--report',required=True);p.add_argument('--repair-output');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);bpy.ops.wm.open_mainfile(filepath=str(ROOT/a.candidate));base=bpy.data.objects['BaiQi_FemaleFoundation'];canonical=base.parent;assert canonical and canonical.type=='ARMATURE' and len(canonical.data.bones)==264
def snapshot():
    return [{'object':o.name,'armature_modifiers':[{'target':m.object.name if m.object else None,'enabled':m.show_viewport and m.show_render,'preserve_volume':m.use_deform_preserve_volume} for m in o.modifiers if m.type=='ARMATURE'],'parent':o.parent.name if o.parent else None} for o in bpy.data.objects if o.type=='MESH']
report={'candidate':a.candidate,'canonical_rig':canonical.name,'armature_objects':[{'name':o.name,'bones':len(o.data.bones),'linked':o.name in bpy.context.scene.objects} for o in bpy.data.objects if o.type=='ARMATURE'],'before':snapshot()}
report['missing_skin_modifiers']=[r['object'] for r in report['before'] if not r['armature_modifiers']]
if a.repair_output:
    rest={b.name:(b.matrix_local.copy(),b.parent.name if b.parent else None) for b in canonical.data.bones}
    for o in [o for o in bpy.data.objects if o.type=='MESH']:
        mods=[m for m in o.modifiers if m.type=='ARMATURE']
        if not mods:mods=[o.modifiers.new('Native adult linear skin restored','ARMATURE')]
        assert len(mods)==1;mods[0].object=canonical;mods[0].show_viewport=True;mods[0].show_render=True;mods[0].use_deform_preserve_volume=False
        world=o.matrix_world.copy();o.parent=canonical;o.matrix_world=world
    for obj in list(bpy.data.objects):
        if obj.type=='ARMATURE' and obj!=canonical:
            assert set(obj.data.bones)==set(canonical.data.bones) or len(obj.data.bones)==264
            bpy.data.objects.remove(obj,do_unlink=True)
    for b in canonical.data.bones:assert rest[b.name]==(b.matrix_local,b.parent.name if b.parent else None)
    out=ROOT/a.repair_output;out.mkdir(parents=True,exist_ok=True);path=out/'BaiQi_Assembly.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path));report['repaired_candidate']=path.relative_to(ROOT).as_posix();report['repaired_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();report['after']=snapshot()
path=ROOT/a.report;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2));print('BAIQI_RIG_BINDING_AUDIT',report['missing_skin_modifiers'],flush=True)
