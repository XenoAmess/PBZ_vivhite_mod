"""Generate the explicit, reviewable v1 project ROM specification."""
import itertools, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
cases=[]
def add(id,title,group,op,values,params=None):
    cases.append(dict(id=id,title=title,group=group,operator=op,parameters=params or {},
        samples=[{'value':v,'label':str(v)+' deg' if isinstance(v,(int,float)) else ', '.join(f'{k}={x}' for k,x in v.items())} for v in values]))
add('neck_pitch','颈部：低头与抬头','neck','neck',[-25,-10,0,20,35],{'axis':'pitch'})
add('neck_yaw','颈部：左右转头','neck','neck',[-60,-30,0,30,60],{'axis':'yaw'})
add('neck_roll','颈部：左右侧倾','neck','neck',[-25,-12,0,12,25],{'axis':'roll'})
add('head_pivot','头骨隔离：俯仰','neck','neck',[-25,-10,0,20,35],{'axis':'pitch','mode':'head_only'})
poses=[dict(pitch=p,yaw=y,roll=r) for p,y,r in itertools.product([-25,0,35],[-60,0,60],[-25,0,25])]
for axis,values in [('pitch',[-12.5,17.5]),('yaw',[-30,30]),('roll',[-12.5,12.5])]:
    for value in values:poses.append(dict(pitch=value if axis=='pitch' else 0,yaw=value if axis=='yaw' else 0,roll=value if axis=='roll' else 0))
for axis,values in [('pitch',[-25,35]),('yaw',[-60,60])]:
    for value in values:poses.append(dict(pitch=value if axis=='pitch' else 0,yaw=value if axis=='yaw' else 0,roll=0,mode='head_only'))
assert len(poses)==37
add('neck_combinations_37','颈部：37个项目组合与隔离姿态','neck','neck',poses)
for id,title,op,values,parameters in [
    ('arms_abduction','双臂：侧平举与高举','abduction',[-35,0,45,85,125],{'sides':['l','r']}),
    ('arm_left','左臂：抬臂','abduction',[0,30,45,85,125],{'sides':['l']}),
    ('arm_right','右臂：抬臂','abduction',[0,30,45,85,125],{'sides':['r']}),
    ('arms_forward','双臂：前伸','forward',[-20,0,30,60,85],{'sides':['l','r']}),
    ('elbows','双肘：屈曲','elbow',[0,30,60,90,120],{'sides':['l','r']}),
    ('arm_twist','上臂：轴向旋转','twist',[-60,-30,0,30,60],{'sides':['l','r']}),
    ('shrug','锁骨：耸肩','shrug',[0,4,8,12,16],{}),
    ('wrists_pitch','双腕：屈伸','wrist',[-45,-20,0,20,45],{'axis':'pitch'}),
    ('wrists_roll','双腕：侧偏','wrist',[-25,-12,0,12,25],{'axis':'roll'}),
    ('fingers','双手：张开至握拳','fingers',[0,.25,.5,.75,1],{}),
    ('guard','组合：前伸屈肘防御','guard',[0,.25,.5,.75,1],{}),
    ('reach_shoulder','组合：交叉触肩','reach',[0,.25,.5,.75,1],{'target':'opposite_shoulder'}),
    ('reach_head','组合：双手触头','reach',[0,.25,.5,.75,1],{'target':'head'})]:
    add(id,title,'arms',op,values,parameters)
for id,title,op,values,parameters in [
    ('spine_pitch','脊柱：前屈后仰','spine',[-15,0,10,20,30],{'axis':'pitch'}),
    ('spine_roll','脊柱：侧屈','spine',[-20,-10,0,10,20],{'axis':'roll'}),
    ('spine_yaw','脊柱：扭转','spine',[-40,-20,0,20,40],{'axis':'yaw'}),
    ('torso_turn','组合：躯干和头反向转动','torso_turn',[-30,-15,0,15,30],{}),
    ('hips_forward','髋：抬腿','hip',[0,25,50,75,100],{'axis':'forward'}),
    ('hips_side','髋：侧抬腿','hip',[0,15,30,45,60],{'axis':'side'}),
    ('hips_twist','髋：轴向旋转','hip',[-30,-15,0,15,30],{'axis':'twist'}),
    ('knees','双膝：屈曲','knee',[0,30,60,90,120],{}),
    ('ankles_pitch','双踝：屈伸','ankle',[-30,-15,0,15,30],{'axis':'pitch'}),
    ('ankles_roll','双踝：内外翻','ankle',[-15,-7.5,0,7.5,15],{'axis':'roll'}),
    ('toes','前脚掌：弯曲','toes',[0,10,20,30,40],{}),
    ('squat','组合：逐级下蹲','squat',[0,.25,.5,.75,1],{})]:
    add(id,title,'body',op,values,parameters)
spec={'schema_version':1,'suite_id':'humanoid_rom','version':'1.0.0',
 'provenance':'Project-designed ROM acceptance set based on sources.json. The 37 neck poses are our parameter grid, not a copy of MetaHuman poses.',
 'units':'degrees; transforms use the input rig unit','skinning':'LINEAR_BLEND',
 'timeline':{'fps':24,'neutral_start':1,'first_sample':13,'sample_step':16,'neutral_hold_frames':16},
 'views':{'neck':['front','side','oblique'],'arms':['front','back','oblique'],'body':['front','side','back']},
 'passes':['clay','textured'],
 'review_rules':{'pose_coverage':'all cases, samples, views and passes required',
    'geometry':'no cracks, spikes, visible volume collapse, detached limbs, neck/collar fusion or deep intersections',
    'neutral':'proportions and silhouette must match the intended character reference',
    'numerical_pass_is_not_visual_acceptance':True},
 'thresholds':{'weight_sum_tolerance':.0001,'neck':{'stretch_p95':1.50,'stretch_max':3.0},
    'shoulder':{'stretch_p95':1.75,'stretch_max':4.0},'elbow':{'stretch_p95':1.75,'stretch_max':3.0}},
 'cases':cases}
path=HERE/'suites/humanoid_v1.json';path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('ROM_SPEC',len(cases),'cases',sum(len(c['samples']) for c in cases),'poses')
