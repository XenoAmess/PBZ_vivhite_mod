"""Author controlled diagnostic actions and sample them without running PBZ.

Rotations are specified in anatomical world axes and converted into each
native bone's rest axes. The sweeps are authored; thumb opposition uses a
documented local rotation reference from one original Soul animation frame.
"""
import argparse, json, math, sys, time
from pathlib import Path
import bpy, numpy as np
from mathutils import Vector, Quaternion
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'scripts'))
from qa.motion_suite import load,sha
from qa_materials import MaterialReview
from qa_rig_preflight import preflight
from qa.anatomy_axes import finger_flexion,thumb_grip
cli=argparse.ArgumentParser()
cli.add_argument('--candidate',default='build/shoulder_inputs/Delta_adult.blend')
cli.add_argument('--output',default='output/live2d_delta/self_test_standard')
cli.add_argument('--suite',default='qa/suites/humanoid_v1_1.json')
cli.add_argument('--metrics-only',action='store_true')
args=cli.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
candidate=(ROOT/args.candidate).resolve();suite=(ROOT/args.suite).resolve();spec=load(suite)
OUT=(ROOT/args.output).resolve();assert OUT.is_relative_to(ROOT);OUT.mkdir(parents=True,exist_ok=True)
hashes={'model':sha(candidate),'suite':sha(suite),'runner':sha(__file__),'contract':sha(ROOT/'qa/motion_suite.py'),
        'materials':sha(ROOT/'scripts/qa_materials.py'),'identity':sha(ROOT/'qa/identity.py'),'character':sha(ROOT/'characters/baiqi/source_contract.json'),
        'rig_preflight':sha(ROOT/'scripts/qa_rig_preflight.py'),'rig_contract':sha(ROOT/'qa/rig_binding.py'),
        'anatomy_axes':sha(ROOT/'qa/anatomy_axes.py'),'native_finger_axes':sha(ROOT/'qa/native_finger_axes.json'),
        'native_thumb_grip':sha(ROOT/'qa/native_thumb_grip.json')}
identity_v2=ROOT/'characters/baiqi/source_contract_v2.json'
if identity_v2.is_file():hashes['character_v2']=sha(identity_v2)
bpy.ops.wm.open_mainfile(filepath=str(candidate))
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
meshes=[o for o in bpy.data.objects if o.type=='MESH' and not o.hide_render]
mesh=next((o for o in meshes if o.name=='BaiQi_FemaleFoundation'),meshes[0])
assert len(arm.data.bones)==264
rig_preflight=preflight(arm,mesh,OUT)
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=512;scene.render.resolution_y=512;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.render.fps=spec['timeline']['fps'];scene.view_settings.view_transform='AgX'
scene.world=bpy.data.worlds.new('Self test studio');scene.world.color=(.10,.10,.10)
for loc,energy,size in [((180,-330,340),2400000,250),((-260,-150,240),1300000,250),((0,260,340),1900000,250)]:
    light=bpy.data.lights.new('SelfTest softbox','AREA');light.energy=energy;light.size=size
    obj=bpy.data.objects.new(light.name,light);scene.collection.objects.link(obj);obj.location=loc
    obj.rotation_euler=(Vector((0,0,158))-obj.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('SelfTest camera');cam=bpy.data.objects.new(data.name,data);scene.collection.objects.link(cam)
scene.camera=cam;data.type='ORTHO';data.clip_end=10000
gray=bpy.data.materials.new('SelfTest clay');gray.use_nodes=True
gray.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.36,.40,.44,1)
gray.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.85
review_materials=MaterialReview(meshes)
controlled=['neck_01','neck_02','head','spine_03','spine_04','spine_05']
controlled += [n+'_'+s for s in ['l','r'] for n in ['clavicle','upperarm','lowerarm']]
controlled += ['pelvis']+[n+'_'+s for s in ['l','r'] for n in ['hand','thigh','calf','foot','ball']]
controlled += [f'{digit}_{joint:02}_{side}' for side in ['l','r'] for digit in ['thumb','index','middle','ring','pinky'] for joint in [1,2,3]]
assert all(n in arm.data.bones for n in controlled),'Rig mapping is incomplete'
for obj in meshes:
    for mod in obj.modifiers:
        if mod.type=='ARMATURE':assert not mod.use_deform_preserve_volume,'Viewport-only dual quaternion skinning is forbidden'
for n in controlled:arm.pose.bones[n].rotation_mode='QUATERNION'
def qaxis(axis,degrees):return Quaternion(Vector(axis).normalized(),math.radians(degrees))
def local(n,world_rotation):
    rest=arm.data.bones[n].matrix_local.to_quaternion()
    arm.pose.bones[n].rotation_quaternion=rest.inverted()@world_rotation@rest
def rotate(n,axis,angle):local(n,qaxis(axis,angle))
def reset():
    for p in arm.pose.bones:p.matrix_basis.identity()
def neck(pitch=0,yaw=0,roll=0,mode='distributed'):
    for n,factor in [('neck_01',.25),('neck_02',.35),('head',.40)]:
        if mode=='head_only':factor=1. if n=='head' else 0.
        local(n,qaxis((0,0,1),yaw*factor)@qaxis((0,1,0),roll*factor)@qaxis((1,0,0),-pitch*factor))
def abduction(side,angle):
    sign=1 if side=='l' else -1
    clav=max(0.,angle-40)*.18
    rotate('clavicle_'+side,(0,1,0),-sign*clav)
    rotate('upperarm_'+side,(0,1,0),-sign*(angle-clav))
def forward(side,angle):
    a=arm.data.bones['upperarm_'+side].head_local;e=arm.data.bones['lowerarm_'+side].head_local
    direction=(e-a).normalized();target=Vector((0,-1,0))
    rotate('upperarm_'+side,direction.cross(target),angle)
def elbow(side,angle):
    a,e,w=[arm.data.bones[n+'_'+side].head_local for n in ['upperarm','lowerarm','hand']]
    direction=(w-e).normalized();target=(-(e-a).normalized()+Vector((0,-.3,0))).normalized()
    rotate('lowerarm_'+side,direction.cross(target),angle)
def twist(side,angle):
    a=arm.data.bones['upperarm_'+side].head_local;e=arm.data.bones['lowerarm_'+side].head_local
    rotate('upperarm_'+side,e-a,angle)
clips=[]
def add(key,title,group,values,apply,labels=None):
    clips.append({'id':key,'title':title,'group':group,'values':values,'apply':apply,
                  'labels':labels or [str(v)+' deg' for v in values]})
add('neck_pitch','颈部：低头至抬头','neck',[-25,-10,0,20,35],lambda v:neck(pitch=v))
add('neck_yaw','颈部：左右转头','neck',[-60,-30,0,30,60],lambda v:neck(yaw=v))
add('neck_roll','颈部：左右侧倾','neck',[-25,-12,0,12,25],lambda v:neck(roll=v))
add('head_pivot','单独头骨：隔离支点与颈部权重','neck',[-25,-10,0,20,35],lambda v:neck(pitch=v,mode='head_only'))
add('neck_diagonal','颈部：转头并抬头','neck',[-1,-.5,0,.5,1],lambda v:neck(pitch=25*abs(v),yaw=45*v,roll=12*v),['L full','L half','Neutral','R half','R full'])
add('arms_abduction','双臂：侧平举至高举','arms',[0,30,45,85,125],lambda v:[abduction(s,v) for s in ['l','r']])
add('arm_left','左臂：单侧抬臂','arms',[0,30,45,85,125],lambda v:abduction('l',v))
add('arm_right','右臂：单侧抬臂','arms',[0,30,45,85,125],lambda v:abduction('r',v))
add('arms_forward','双臂：向前抬起','arms',[0,20,40,60,85],lambda v:[forward(s,v) for s in ['l','r']])
add('elbows','双肘：逐级弯曲','arms',[0,30,60,90,120],lambda v:[elbow(s,v) for s in ['l','r']])
add('arm_twist','上臂：轴向旋转','arms',[-60,-30,0,30,60],lambda v:[twist(s,v*(1 if s=='l' else -1)) for s in ['l','r']])
def shrug(v):
    rotate('clavicle_l',(0,1,0),-v);rotate('clavicle_r',(0,1,0),v)
add('shrug','肩膀：耸肩','arms',[0,4,8,12,16],shrug)
def guard(v):
    for s in ['l','r']:forward(s,70*v);elbow(s,95*v)
    neck(yaw=30*v,pitch=10*v)
add('guard','组合：前伸、屈肘与转头','arms',[0,.25,.5,.75,1],guard,['Rest','25%','50%','75%','Full'])
def torso(v):
    for n,k in [('spine_03',.25),('spine_04',.35),('spine_05',.4)]:rotate(n,(0,0,1),v*k)
    neck(yaw=-v*.5)
add('torso_turn','组合：转身与反向转头','neck',[-30,-15,0,15,30],torso)

def limb_axis(side,kind):
    hand=arm.data.bones['hand_'+side].head_local
    middle=arm.data.bones['middle_01_'+side].head_local
    lateral=(arm.data.bones['index_01_'+side].head_local-arm.data.bones['pinky_01_'+side].head_local).normalized()
    normal=lateral.cross((middle-hand).normalized()).normalized()
    if normal.y>0:normal=-normal
    return lateral if kind=='pitch' else normal
def reach(side,amount,target_kind):
    if amount==0:return
    sign=1 if side=='l' else -1
    a,e,w=[arm.data.bones[n+'_'+side].head_local.copy() for n in ['upperarm','lowerarm','hand']]
    target=Vector((-sign*17,-14,150)) if target_kind=='opposite_shoulder' else Vector((sign*20,-12,182))
    target=w.lerp(target,amount);delta=target-a;distance=delta.length
    l1=(e-a).length;l2=(w-e).length;distance=min(l1+l2-.01,max(abs(l1-l2)+.01,distance));direction=delta.normalized()
    x=(l1*l1-l2*l2+distance*distance)/(2*distance);height=math.sqrt(max(0,l1*l1-x*x))
    rest_pole=e-a-direction*(e-a).dot(direction)
    wanted=Vector((sign*.4,-.8,-.25));pole=rest_pole.normalized().lerp(wanted.normalized(),amount)
    pole=(pole-direction*pole.dot(direction)).normalized()
    desired_e=a+direction*x+pole*height
    upper_q=(e-a).normalized().rotation_difference((desired_e-a).normalized())
    local('upperarm_'+side,upper_q)
    target_pre_parent=upper_q.inverted()@(target-desired_e).normalized()
    local('lowerarm_'+side,(w-e).normalized().rotation_difference(target_pre_parent))
def apply_case(case,value):
    op=case['operator'];p=case['parameters'];sides=p.get('sides',['l','r'])
    if op=='neck':
        if isinstance(value,dict):neck(**value)
        else:neck(**{p['axis']:value},mode=p.get('mode','distributed'))
    elif op in ['abduction','forward','elbow','twist']:
        function={'abduction':abduction,'forward':forward,'elbow':elbow,'twist':twist}[op]
        for side in sides:function(side,value*(-1 if op=='twist' and side=='r' else 1))
    elif op=='shrug':shrug(value)
    elif op=='guard':guard(value)
    elif op=='torso_turn':torso(value)
    elif op=='reach':
        for side in sides:reach(side,value,p['target'])
    elif op=='wrist':
        for side in sides:rotate('hand_'+side,limb_axis(side,p['axis']),value)
    elif op=='fingers':
        for side in sides:
            normal=Vector(finger_flexion(side))
            for digit in ['index','middle','ring','pinky']:
                for joint,angle in [(1,55),(2,80),(3,55)]:
                    name=f'{digit}_{joint:02}_{side}';position=arm.data.bones[name].head_local
                    if joint<3:direction=arm.data.bones[f'{digit}_{joint+1:02}_{side}'].head_local-position
                    else:direction=position-arm.data.bones[f'{digit}_02_{side}'].head_local
                    rotate(name,direction.normalized().cross(normal),angle*value)
            for joint in [1,2,3]:
                name=f'thumb_{joint:02}_{side}'
                arm.pose.bones[name].rotation_quaternion=Quaternion((1,0,0,0)).slerp(Quaternion(thumb_grip(name)),value)
    elif op=='spine':
        axis={'pitch':(1,0,0),'roll':(0,1,0),'yaw':(0,0,1)}[p['axis']]
        for n,k in [('spine_03',.25),('spine_04',.35),('spine_05',.40)]:rotate(n,axis,value*k)
    elif op in ['hip','knee','ankle','toes','squat']:
        for side in sides:
            sign=1 if side=='l' else -1
            thigh,calf,foot=[arm.data.bones[n+'_'+side].head_local for n in ['thigh','calf','foot']]
            if op in ['hip','squat']:
                axis_name=p.get('axis','forward');direction=(calf-thigh).normalized()
                axis=direction if axis_name=='twist' else direction.cross(Vector((sign,0,0)) if axis_name=='side' else Vector((0,-1,0)))
                rotate('thigh_'+side,axis,60*value if op=='squat' else value)
            if op in ['knee','squat']:rotate('calf_'+side,(foot-calf).normalized().cross(Vector((0,1,0))),110*value if op=='squat' else value)
            if op in ['ankle','squat']:rotate('foot_'+side,(1,0,0) if p.get('axis','pitch')=='pitch' else (0,1,0),-50*value if op=='squat' else value)
            if op=='toes':rotate('ball_'+side,(1,0,0),-value)
        if op=='squat':
            drop=(calf-thigh).length*(1-math.cos(math.radians(60*value)))+(foot-calf).length*(1-math.cos(math.radians(50*value)))
            arm.pose.bones['pelvis'].location=arm.data.bones['pelvis'].matrix_local.to_quaternion().inverted()@Vector((0,0,-drop))
    else:raise ValueError('Unknown ROM operator: '+op)
clips=[]
for case in spec['cases']:
    clips.append({'id':case['id'],'title':case['title'],'group':case['group'],
        'values':[s['value'] for s in case['samples']],'labels':[s['label'] for s in case['samples']],
        'apply':lambda value,case=case:apply_case(case,value)})

arm.animation_data_create();arm.animation_data.action=None;reset();bpy.context.view_layer.update()
rest=np.array([(mesh.matrix_world@v.co)[:] for v in mesh.data.vertices])
regions={
 'neck':(abs(rest[:,0])<5.5)&(rest[:,2]>157)&(rest[:,2]<166)&(rest[:,1]>-.5)&(rest[:,1]<10),
 'shoulder':(abs(rest[:,0])>12)&(abs(rest[:,0])<27)&(rest[:,2]>144)&(rest[:,2]<157),
 'elbow':(abs(rest[:,0])>33)&(abs(rest[:,0])<44)&(rest[:,2]>126)&(rest[:,2]<138)}
edges=np.array([e.vertices[:] for e in mesh.data.edges]);lengths=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1)
region_edges={n:edges[mask[edges[:,0]]&mask[edges[:,1]]&(lengths>.03)] for n,mask in regions.items()}
rest_lengths={n:np.linalg.norm(rest[e[:,0]]-rest[e[:,1]],axis=1) for n,e in region_edges.items()}
def evaluate():
    bpy.context.view_layer.update();obj=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());data=obj.to_mesh()
    coords=np.array([(mesh.matrix_world@v.co)[:] for v in data.vertices]);obj.to_mesh_clear();assert np.isfinite(coords).all();return coords
def metrics(coords):
    result={}
    for n,e in region_edges.items():
        ratio=np.linalg.norm(coords[e[:,0]]-coords[e[:,1]],axis=1)/rest_lengths[n]
        result[n]={'edges':len(e),'stretch_p95':float(np.percentile(ratio,95)),
                   'stretch_max':float(ratio.max()),'compression_p05':float(np.percentile(ratio,5))}
    return result
weight_sums=[sum(g.weight for g in v.groups) for o in meshes for v in o.data.vertices]
assert min(weight_sums)>1-spec['thresholds']['weight_sum_tolerance'] and max(weight_sums)<1+spec['thresholds']['weight_sum_tolerance']
report={'model':str(candidate.relative_to(ROOT)),'input_hashes':hashes,'suite_version':spec['version'],'suite_path':suite.relative_to(ROOT).as_posix(),
 'native_input':str(candidate.relative_to(ROOT)),'bones':264,'case_ids':[c['id'] for c in spec['cases']],
 'purpose':'controlled offline diagnosis; no game process launched',
 'axis_convention':'native Z up; -Y front; character left is +X; neck pitch positive means up',
 'angle_note':'arm abduction is rotation from the native A pose, not from arms-down; these are chosen diagnostic ranges, not anatomical limits',
 'neck_distribution':{'neck_01':.25,'neck_02':.35,'head':.40},
 'metrics_note':'edge length changes flag frames for visual inspection; they do not establish good anatomy or visual acceptance',
 'visible_meshes':[o.name for o in meshes],'numerical_metric_mesh':mesh.name,'clay_preserves_alpha':True,'rig_preflight':rig_preflight,
 'clips':[],'user_visual_acceptance':False}
actions={}
for clip in clips:
    action=bpy.data.actions.new('DeltaTest_'+clip['id']);action.use_fake_user=True
    arm.animation_data.action=action;actions[clip['id']]=action
    frames=[]
    # Neutral holds bracket each sweep; sample markers correspond to the five
    # authored targets, not interpolated or cherry-picked game frames.
    for index,value in enumerate(clip['values']):
        frame=spec['timeline']['first_sample']+index*spec['timeline']['sample_step'];scene.frame_set(frame);reset();clip['apply'](value)
        for n in controlled:arm.pose.bones[n].keyframe_insert(data_path='rotation_quaternion',frame=frame,group=n)
        arm.pose.bones['pelvis'].keyframe_insert(data_path='location',frame=frame,group='pelvis')
        frames.append(frame)
    end_frame=frames[-1]+spec['timeline']['neutral_hold_frames']
    for frame in [spec['timeline']['neutral_start'],end_frame]:
        scene.frame_set(frame);reset()
        for n in controlled:arm.pose.bones[n].keyframe_insert(data_path='rotation_quaternion',frame=frame,group=n)
        arm.pose.bones['pelvis'].keyframe_insert(data_path='location',frame=frame,group='pelvis')
    if action.slots:
        for layer in action.layers:
            for strip in layer.strips:
                bag=strip.channelbag(action.slots[0])
                if bag:
                    for fc in bag.fcurves:
                        for key in fc.keyframe_points:key.interpolation='LINEAR'
    row={'id':clip['id'],'title':clip['title'],'group':clip['group'],'action':action.name,'frame_range':[1,end_frame],
         'samples':[],'images':[]}
    for i,(frame,value) in enumerate(zip(frames,clip['values'])):
        scene.frame_set(frame);coords=evaluate()
        row['samples'].append({'frame':frame,'value':value,'label':clip['labels'][i],'metrics':metrics(coords)})
    report['clips'].append(row)
print('SELFTEST_ACTIONS_AUTHORED',len(clips),flush=True)

def set_pass(kind):
    review_materials.apply(kind)
def view(group,name):
    z=168 if group=='neck' else 147 if group=='arms' else 110
    data.ortho_scale=68 if group=='neck' else 185 if group=='arms' else 260
    loc={'front':(0,-500,z+2),'side':(500,0,z+2),'back':(0,500,z+2),'oblique':(330,-420,z+4)}[name]
    cam.location=loc;cam.rotation_euler=(Vector((0,0,z))-cam.location).to_track_quat('-Z','Y').to_euler()
for clip,row in zip(clips,report['clips']):
    if args.metrics_only:continue
    arm.animation_data.action=actions[clip['id']]
    views=spec['views'][clip['group']]
    # Full clay grids establish shape; textured grids expose material seams
    # for neck tests and representative arm/combined tests.
    passes=spec['passes']
    for kind in passes:
        set_pass(kind)
        for sample_index,sample in enumerate(row['samples']):
            scene.frame_set(sample['frame']);bpy.context.view_layer.update()
            for name in views:
                view(clip['group'],name)
                relative=Path('samples')/clip['id']/kind/(f'{sample_index:02}_{name}.png')
                path=OUT/relative;path.parent.mkdir(parents=True,exist_ok=True)
                scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
                row['images'].append({'pass':kind,'view':name,'sample':sample_index,'path':relative.as_posix()})
    print('SELFTEST_SAMPLED',clip['id'],len(row['images']),flush=True)
    (OUT/'sampling_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

set_pass('textured');arm.animation_data.action=actions['neck_pitch'];scene.frame_set(45)
scene.frame_start=1;scene.frame_end=93;view('neck','oblique')
for marker in list(scene.timeline_markers):scene.timeline_markers.remove(marker)
for i,frame in enumerate([13,29,45,61,77]):scene.timeline_markers.new(['Down -25','Down -10','Neutral','Up +20','Up +35'][i],frame=frame)
failures=[]
for clip in report['clips']:
    for sample in clip['samples']:
        for region,limits in spec['thresholds'].items():
            if not isinstance(limits,dict):continue
            for metric,limit in limits.items():
                value=sample['metrics'][region][metric]
                if value>limit:failures.append({'case':clip['id'],'frame':sample['frame'],'region':region,'metric':metric,'value':value,'limit':limit})
report['coverage_complete']=all(len(c['images'])==len(c['samples'])*len(spec['views'][c['group']])*len(spec['passes']) for c in report['clips'])
report['numerical_checks_passed']=not failures;report['failures']=failures
report['status']='failed' if failures else 'pending_review'
mesh['self_test_note']=f"{len(clips)} independent authored diagnostic actions; no game runtime claim"
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Delta_SelfTest.blend'))
(OUT/'sampling_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('SELFTEST_SUITE_READY',OUT,flush=True)
