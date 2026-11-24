"""Render a reproducible whole-body neutral-shape inspection before ROM QA."""
import argparse,hashlib,json,math,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from qa_materials import MaterialReview
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--output',required=True);p.add_argument('--suite',default='qa/shape_audit_v1.json')
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=(ROOT/args.output).resolve();assert out.is_relative_to(ROOT);out.mkdir(parents=True,exist_ok=True)
config=ROOT/args.suite;spec=json.loads(config.read_text(encoding='utf-8'));candidate=ROOT/args.candidate
bpy.ops.wm.open_mainfile(filepath=str(candidate));meshes=[o for o in bpy.data.objects if o.type=='MESH' and not o.hide_render];mesh=next((o for o in meshes if o.name=='BaiQi_FemaleFoundation'),meshes[0]);arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
if arm.animation_data:arm.animation_data_clear()
for bone in arm.pose.bones:bone.matrix_basis.identity()
for obj in meshes:
    for mod in obj.modifiers:
        if mod.type=='ARMATURE':assert not mod.use_deform_preserve_volume
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False;scene.view_settings.view_transform='AgX'
scene.world=bpy.data.worlds.new('Shape audit studio');scene.world.color=(.10,.10,.10)
for loc,energy,size in [((180,-330,340),2400000,250),((-260,-150,240),1300000,250),((0,260,340),1900000,250)]:
    data=bpy.data.lights.new('Shape audit softbox','AREA');data.energy=energy;data.size=size
    obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.location=loc;obj.rotation_euler=(Vector((0,0,145))-obj.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('Shape audit camera');cam=bpy.data.objects.new(data.name,data);scene.collection.objects.link(cam);scene.camera=cam;data.type='ORTHO';data.clip_end=10000
clay=bpy.data.materials.new('Shape audit clay');clay.use_nodes=True;clay.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.36,.40,.44,1);clay.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.85
review_materials=MaterialReview(meshes);images=[]
def render(section,target,scale,angle,kind,full=False):
    radians=math.radians(angle);t=Vector(target);cam.location=t+Vector((500*math.sin(radians),-500*math.cos(radians),0));cam.rotation_euler=(t-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
    scene.render.resolution_x=1200 if full else 768;scene.render.resolution_y=1200 if full else 768
    folder=out/section/kind;folder.mkdir(parents=True,exist_ok=True);path=folder/f'{angle:03}.png';scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
    images.append({'section':section,'pass':kind,'angle_deg':angle,'path':path.relative_to(out).as_posix()})
for kind in spec['passes']:
    review_materials.apply(kind)
    full=spec['full_body']
    for angle in full['angles_deg']:render('full_body',full['target'],full['scale'],angle,kind,True)
    for section in spec['sections']:
        for angle in spec['detail_views_deg']:render(section['id'],section['target'],section['scale'],angle,kind)
review_materials.apply('textured')
coords=np.array([o.matrix_world@v.co for o in meshes for v in o.data.vertices]);head=[o.matrix_world@v.co for o in meshes if o.vertex_groups.get('head') for v in o.data.vertices if any(g.group==o.vertex_groups['head'].index and g.weight>.999 for g in v.groups)]
lengths={}
for side in ['l','r']:
    for name,a,b in [('upper_arm','upperarm','lowerarm'),('forearm','lowerarm','hand'),('thigh','thigh','calf'),('calf','calf','foot'),('palm','hand','middle_01')]:
        lengths[name+'_'+side]=float((arm.data.bones[a+'_'+side].head_local-arm.data.bones[b+'_'+side].head_local).length)
report={'schema_version':1,'shape_suite_version':spec['version'],'candidate':args.candidate,'input_hashes':{'model':hashlib.sha256(candidate.read_bytes()).hexdigest(),'suite':hashlib.sha256(config.read_bytes()).hexdigest(),'runner':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'materials':hashlib.sha256((ROOT/'scripts/qa_materials.py').read_bytes()).hexdigest()},
    'images':images,'expected_images':len(spec['passes'])*(len(spec['full_body']['angles_deg'])+len(spec['sections'])*len(spec['detail_views_deg'])),'sections':[s['id'] for s in spec['sections']],
    'bounds_cm':{'min':coords.min(axis=0).tolist(),'max':coords.max(axis=0).tolist()},'head_with_hair_bounds_cm':{'min':np.min(head,axis=0).tolist(),'max':np.max(head,axis=0).tolist()},'native_bone_lengths_cm':lengths,
    'measurement_limit':'Native bone lengths describe the rig, not the visible limb contours. Head bounds include hair and ornaments.',
    'visible_meshes':[o.name for o in meshes],'clay_preserves_alpha':True,'status':'pending_visual_review','game_runtime_allowed':False}
assert len(images)==report['expected_images'];report['coverage_complete']=True
(out/'shape_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8');bpy.ops.wm.save_as_mainfile(filepath=str(out/'Delta_ShapeAudit.blend'))
print('SHAPE_AUDIT_READY',len(images),'images',flush=True)
