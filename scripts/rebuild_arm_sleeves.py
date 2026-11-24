"""Build centered, regular sleeve/elbow/forearm rings around native joints.

Uses newly generated geometry, not the game's arm surface. Keeps the existing
body, head and native-joint hands for a directly comparable shoulder review.
"""
import json
import math
import sys
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/live2d_delta/shoulder_rebuild';OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'output/live2d_delta/hunyuan21_polished/Delta_live2d.blend'))
mesh=next(o for o in bpy.data.objects if o.type=='MESH')
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
ownership=np.load(ROOT/'artifacts/live2d/arm_ownership.npy')
head_visible=np.load(ROOT/'artifacts/live2d/head_visible.npy')
PRESERVE='--preserve-yoke' in sys.argv
FIT_EXISTING='--fit-existing' in sys.argv
neck_mask=None
if PRESERVE:
    neck_mask=np.load(ROOT/'artifacts/live2d/neck_visible.npy')
bm=bmesh.new();bm.from_mesh(mesh.data)
uv=bm.loops.layers.uv.active;deform=bm.verts.layers.deform.verify()
groups={g.name:g.index for g in mesh.vertex_groups}
def group(name):
    if name not in groups:groups[name]=mesh.vertex_groups.new(name=name).index
    return groups[name]
def point(name):return mesh.matrix_world.inverted()@(arm.matrix_world@arm.data.bones[name].head_local)
def smooth(t):t=max(0.,min(1.,t));return t*t*(3.-2.*t)
def source(loop):
    u,v=loop[uv].uv;return float(u*1400),float((1-v)*2200)
def own(x,y):return float(ownership[min(2199,max(0,round(y))),min(1399,max(0,round(x)))])
report={'method':'new ring topology centered on native shoulder, elbow and wrist','sides':{}}
# The inferred neck/collar was a single funnel, partly weighted to the head.
# Remove that entire non-head yoke instead of trying to hide it with normals.
remove=[]
for face in bm.faces:
    x,y=np.mean([source(loop) for loop in face.loops],axis=0)
    head=head_visible[min(2199,max(0,round(y))),min(1399,max(0,round(x)))]
    if not PRESERVE and 602<y<754 and abs(x-694.5)<215 and not (head and y<630):remove.append(face)
report['old_neck_yoke_faces_removed']=len(remove)
bmesh.ops.delete(bm,geom=remove,context='FACES')
for v in bm.verts:
    if not v.link_loops:continue
    x,y=source(v.link_loops[0])
    is_head=y<599 or (y<630 and abs(x-694.5)>48 and head_visible[min(2199,max(0,round(y))),min(1399,max(0,round(x)))])
    if is_head:
        v.co.z-=.100 if PRESERVE else .025
        v.co.y=.05+(v.co.y-.05)*.85
        v[deform].clear();v[deform][group('head')]=1.
    elif PRESERVE and 595<y<825 and abs(x-694.5)<220:
        v.co.z-=float(np.interp(y,[595,620,640,660,680,700,720,740,760,780,800,825],[.100,.090,.075,.062,.050,.040,.030,.024,.017,.010,.004,0.]))
        is_neck=neck_mask[min(2199,max(0,round(y))),min(1399,max(0,round(x)))]
        if is_neck and y<670:
            v.co.x=(x-694.5)*.00125
            v.co.y=.05+max(-.033,min(.033,v.co.y-.05))
            mix=smooth((v.co.z-1.61)/.065)
            weights={'neck_01':1-mix,'neck_02':mix*.7,'head':mix*.3}
        else:
            shoulder=.70*smooth((abs(v.co.x)-.06)/.12)*smooth((v.co.z-1.43)/.08)
            weights={'spine_05':1-shoulder,'clavicle_'+('l' if v.co.x>=0 else 'r'):shoulder}
        v[deform].clear()
        for name,value in weights.items():
            if value>1e-6:v[deform][group(name)]=value
for side,sign in [('l',1),('r',-1)]:
    a,e,w=[point(name+'_'+side) for name in ['upperarm','lowerarm','hand']]
    axis=(e-a).normalized();upper=(e-a).length;fore=(w-e).length;length=upper+fore
    if FIT_EXISTING:
        candidates=[]
        for v in bm.verts:
            if not v.link_loops:continue
            x,y=source(v.link_loops[0]);o=own(x,y)
            if sign*(x-694.5)<70 or not 695<y<1047 or o<.20:continue
            if side=='r' and 735<y<825 and x<520:continue
            p=np.array([sign*(x-694.5),y])
            if y<875:
                d2=np.array([84.,155.]);t=float((p-np.array([136.,720.]))@d2/(d2@d2));s=t*upper
                c=a+(e-a)*t;direction=axis
            else:
                d2=np.array([90.,165.]);t=float((p-np.array([220.,875.]))@d2/(d2@d2));s=upper+t*fore
                c=e+(w-e)*t;direction=(w-e).normalized()
            q=v.co-c;radial=q-direction*q.dot(direction)
            candidates.append((v,x,y,o,s,c,direction,radial.copy()))
        station=np.array([q[4] for q in candidates]);radial=np.array([q[7][:] for q in candidates])
        radii=sorted([(-.07,.047),(0.,.052),(.055,.049),(.13,.043),
            (upper-.04,.035),(upper,.033),(upper+.04,.036),
            (upper+fore*.35,.040),(upper+fore*.48,.042),
            (upper+fore*.55,.028),(upper+fore*.75,.026),(length+.01,.0235)])
        for index,(v,x,y,o,s,c,direction,q) in enumerate(candidates):
            nearby=np.abs(station-s)<.030
            center=np.mean(radial[nearby],axis=0)
            q-=Vector(center);q-=direction*q.dot(direction)
            if q.length<1e-5:continue
            radius=float(np.interp(s,[r[0] for r in radii],[r[1] for r in radii]))
            # Keep the source's cuff folds but center the sleeve around the
            # joint. The connected source surface keeps an intact shoulder.
            detail=max(-.003,min(.003,(q.length-radius)*.15))
            target=c+q.normalized()*(radius+detail)
            influence=smooth((o-.20)/.55)*smooth((s+.07)/.11)
            v.co=v.co.lerp(target,influence)
            elbow=smooth((s-upper+.045)/.09);shoulder=.70*smooth((.07-s)/.13)
            weights={'upperarm_'+side:(1-elbow)*(1-shoulder),'clavicle_'+side:(1-elbow)*shoulder,'lowerarm_'+side:elbow}
            twist=.65*smooth((s-upper-.04)/.13)
            weights['lowerarm_twist_01_'+side]=weights['lowerarm_'+side]*twist;weights['lowerarm_'+side]*=1-twist
            old=dict(v[deform]);v[deform].clear()
            for gi,val in old.items():v[deform][gi]=val*(1-influence)
            for name,value in weights.items():
                gi=group(name);v[deform][gi]=v[deform].get(gi,0.)+value*influence
        report['sides'][side]={'centered_source_vertices':len(candidates),'surface_connectivity_preserved':True,
            'native_upperarm_m':upper,'native_forearm_m':fore}
        continue
    cut=a+axis*.040
    faces=[];ribbon=[]
    for f in bm.faces:
        pixels=[source(loop) for loop in f.loops]
        x,y=np.mean(pixels,axis=0)
        if sign*(x-694.5)<78 or not (695<y<1080):continue
        ownership_value=sum(own(px,py) for px,py in pixels)/len(pixels)
        c=f.calc_center_median()
        if ownership_value<.08 or (c-cut).dot(axis)<0:continue
        # Preserve the blue upper-sleeve ribbon; it has no anatomical role.
        if side=='r' and 735<y<825 and x<520:
            ribbon.append(f);continue
        faces.append(f)
    removed=len(faces)
    bmesh.ops.delete(bm,geom=faces,context='FACES')
    # Recenter the retained short shoulder socket, fading to the untouched
    # torso. This fixes the inferred arm volume being offset from its pivot.
    root_changes=0
    for v in bm.verts:
        if not v.link_loops:continue
        x,y=source(v.link_loops[0])
        if sign*(x-694.5)<75 or not (700<y<765):continue
        ownership_value=own(x,y)
        t=(v.co-a).dot(axis)
        if not (-.055<t<.080):continue
        radial=v.co-a-axis*t
        if radial.length<1e-6:continue
        influence=smooth(ownership_value)*smooth((t+.055)/.07)
        target_radius=.047
        target=a+axis*t+radial.normalized()*target_radius
        v.co=v.co.lerp(target,influence*.8);root_changes+=1
        v[deform].clear()
        upper_weight=.55+.4*smooth((t+.02)/.07)
        v[deform][group('upperarm_'+side)]=upper_weight
        v[deform][group('clavicle_'+side)]=1-upper_weight
    # Dense anatomical rings at the cap and elbow; straight spans stay simple.
    stations=sorted(set([-.070,-.050,-.035,-.018,0.,.014,.028,.045,.065,.09,.12,.16,.20,
        upper-.06,upper-.04,upper-.025,upper-.012,upper,upper+.012,upper+.025,
        upper+.04,upper+.06,upper+fore*.30,upper+fore*.40,upper+fore*.46,
        upper+fore*.52,upper+fore*.62,upper+fore*.72,upper+fore*.82,
        upper+fore*.90,upper+fore*.97,length,length+.006]))
    radius_points=[(-.070,.040),(-.050,.049),(-.035,.050),(-.018,.051),(0.,.051),(.045,.050),(.12,.045),
        (upper-.05,.037),(upper,.032),(upper+.035,.035),
        (upper+fore*.30,.039),(upper+fore*.46,.041),
        (upper+fore*.52,.030),(upper+fore*.72,.028),
        (upper+fore*.90,.025),(length+.006,.024)]
    radius_points=sorted(radius_points)
    rings=[]
    for s in stations:
        if s<=upper:
            t=s/upper;center=a+(e-a)*t;direction=(e-a).normalized()
            sx=694.5+sign*(136+(220-136)*t);sy=720+(875-720)*t
        else:
            t=(s-upper)/fore;center=e+(w-e)*t;direction=(w-e).normalized()
            sx=694.5+sign*(220+(310-220)*t);sy=875+(1040-875)*t
        # Transport the cross section smoothly through the rest-pose elbow.
        blend=smooth((s-upper+.035)/.07)
        tangent=(axis*(1-blend)+(w-e).normalized()*blend).normalized()
        back=Vector((0,1,0));back=(back-tangent*back.dot(tangent)).normalized()
        up=tangent.cross(back).normalized()*sign
        radius=float(np.interp(s,[p[0] for p in radius_points],[p[1] for p in radius_points]))
        elbow=smooth((s-upper+.032)/.064)
        shoulder=.55*smooth((.055-s)/.075)
        weights={'upperarm_'+side:(1-elbow)*(1-shoulder),'clavicle_'+side:(1-elbow)*shoulder,
                 'lowerarm_'+side:elbow}
        if s>upper+.06:
            twist=.75*smooth((s-upper-.04)/.12)
            weights['lowerarm_twist_01_'+side]=weights['lowerarm_'+side]*twist
            weights['lowerarm_'+side]*=1-twist
        wrist=.4*smooth((s-length+.04)/.045)
        if wrist:
            weights={n:value*(1-wrist) for n,value in weights.items()}
            weights['hand_'+side]=wrist
        ring=[]
        for j in range(32):
            angle=2*math.pi*j/32
            radial=up*math.cos(angle)+back*math.sin(angle)
            v=bm.verts.new(center+radial*radius)
            for name,value in weights.items():
                if value>1e-6:v[deform][group(name)]=value
            ring.append(v)
        if rings:
            previous=rings[-1]
            for j in range(32):
                f=bm.faces.new([previous[j],previous[(j+1)%32],ring[(j+1)%32],ring[j]])
                f.smooth=True
                f.material_index=0 if math.sin(2*math.pi*(j+.5)/32)<0 else 2
                for loop in f.loops:
                    pos=loop.vert.co
                    # Locate this corner's ring station, preserving wrist/cuff
                    # bands at equal arc positions on front and back surfaces.
                    now=loop.vert in ring
                    ss=s if now else stations[len(rings)-1]
                    if ss<=upper:
                        tt=ss/upper;cx=694.5+sign*(136+84*tt);cy=720+155*tt
                    else:
                        tt=(ss-upper)/fore;cx=694.5+sign*(220+90*tt);cy=875+165*tt
                    jj=ring.index(loop.vert) if now else previous.index(loop.vert)
                    offset=math.cos(2*math.pi*jj/32)
                    half_width=25. if cy<880 else 27. if cy<950 else 13.
                    dx,dy=(84.,155.) if cy<875 else (90.,165.)
                    norm=math.hypot(dx,dy)
                    loop[uv].uv=((cx+sign*dy/norm*half_width*offset)/1400,
                                     1-(cy-dx/norm*half_width*offset)/2200)
        rings.append(ring)
    # Capped roots overlap inside the jacket and existing native-joint palms.
    for ring,reverse in [(rings[0],True),(rings[-1],False)]:
        f=bm.faces.new(ring[::-1] if reverse else ring);f.material_index=2
        for loop in f.loops:loop[uv].uv=(.99,.01)
    report['sides'][side]={'old_faces_removed':removed,'root_vertices_recentered':root_changes,
        'new_rings':len(rings),'ring_vertices':32,'upperarm_length_m':upper,'forearm_length_m':fore,
        'upper_to_forearm_ratio':upper/fore,'note':'joint lengths retained; garment volume and elbow loops rebuilt'}

# A separate, short neck and rounded clavicular yoke. The native spine is
# posterior to the chest surface; do not use the spine location as the entire
# garment cross-section center.
def loft(specifications,segments,neck=False):
    previous=None
    for z,rx,ry,cy,sy in specifications:
        ring=[]
        for j in range(segments):
            angle=2*math.pi*j/segments
            x=rx*math.cos(angle);y=cy+ry*math.sin(angle)
            v=bm.verts.new((x,y,z))
            if neck:
                head_mix=.65*smooth((z-1.665)/.055)
                high=smooth((z-1.62)/.07)
                weights={'neck_01':1-high,'neck_02':high*(1-head_mix),'head':high*head_mix}
            else:
                shoulder=.78*smooth((abs(x)-.055)/.11)*smooth((z-1.45)/.07)
                neck_mix=.30*smooth((z-1.55)/.07)*(1-shoulder)
                weights={'spine_05':1-shoulder-neck_mix,'clavicle_'+('l' if x>=0 else 'r'):shoulder,'neck_01':neck_mix}
            for name,value in weights.items():
                if value>1e-6:v[deform][group(name)]=value
            ring.append(v)
        if previous:
            for j in range(segments):
                face=bm.faces.new([previous[j],previous[(j+1)%segments],ring[(j+1)%segments],ring[j]])
                face.smooth=True
                face.material_index=6 if neck else (0 if math.sin(2*math.pi*(j+.5)/segments)<0 else 2)
                for loop in face.loops:
                    if neck:loop[uv].uv=(.99,.01)
                    else:
                        zz=loop.vert.co.z
                        yy=float(np.interp(zz,[s[0] for s in specifications],[s[4] for s in specifications]))
                        loop[uv].uv=((694.5+loop.vert.co.x/.00143)/1400,1-yy/2200)
        previous=ring

if not PRESERVE:loft([(1.452,.176,.121,-.006,765),(1.47,.181,.120,-.004,750),
      (1.49,.191,.111,.002,730),(1.51,.199,.099,.012,710),
      (1.529,.201,.084,.027,690),(1.545,.183,.073,.037,672),
      (1.561,.151,.061,.042,655),(1.577,.117,.051,.045,643),
      (1.593,.081,.043,.046,634),(1.607,.053,.038,.046,627),
      (1.620,.039,.034,.046,620)],48)
if not PRESERVE:loft([(1.602,.036,.032,.046,640),(1.620,.035,.031,.047,635),
      (1.645,.033,.030,.047,628),(1.670,.032,.029,.048,620),
      (1.694,.033,.030,.048,612),(1.714,.036,.032,.049,604),
      (1.729,.043,.037,.050,600)],32,neck=True)
report['neck_yoke']='original garment preserved, neck/head fitting corrected 100 mm' if PRESERVE else 'separate neck with rounded trapezius/clavicle rings; head lowered 25 mm'
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
bm.to_mesh(mesh.data);bm.free();mesh.data.update()
sys.path.insert(0,str(ROOT/'scripts'))
from delta_surface_normals import soften_face_normals
soften_face_normals(mesh)
mesh['shoulder_rebuild']='regular centered sleeve rings with clavicle/elbow weight gradients'
mesh['limits']='Root and wrist overlap seams require visual review; this candidate is not accepted'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Delta_live2d.blend'))
(OUT/'shoulder_rebuild.json').write_text(json.dumps(report,indent=2))
print('SHOULDER_REBUILD_PREVIEW',json.dumps(report))
