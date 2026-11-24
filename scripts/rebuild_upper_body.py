"""Reconstruct the neck, shoulder yoke and sleeves as one continuous surface.

The source head anchor was at the chin rather than the native ear pivot.
This moves the head, preserves the original lower outfit and hands, and builds
an independent garment volume. All geometry here is generated, not game mesh.
"""
import json, math, sys
from pathlib import Path
import bpy, bmesh, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/live2d_delta/shoulder_rebuild';OUT.mkdir(exist_ok=True)
if '--output' in sys.argv:
    OUT=(ROOT/sys.argv[sys.argv.index('--output')+1]).resolve()
    assert OUT.is_relative_to(ROOT);OUT.mkdir(parents=True,exist_ok=True)
ANATOMICAL='--anatomical-neck' in sys.argv
KEEP_FACE='--keep-face-shell' in sys.argv
ORIGINAL_HEAD='--original-head' in sys.argv
RELAX_FACE='--relax-face' in sys.argv
if RELAX_FACE:ORIGINAL_HEAD=True
CLEAN_FACE='--clean-face' in sys.argv
FLAT_COLLAR='--flat-collar' in sys.argv
if ORIGINAL_HEAD:KEEP_FACE=True
HEAD_PROFILE=[(1.638,.007,.010,-.045,600),(1.648,.030,.035,-.015,592),
      (1.660,.052,.065,.020,582),(1.680,.072,.095,.035,567),
      (1.705,.087,.120,.045,546),(1.735,.100,.130,.050,522),
      (1.765,.106,.140,.052,498),(1.795,.108,.140,.055,473),
      (1.825,.103,.135,.060,448),(1.855,.092,.115,.065,424),
      (1.885,.074,.080,.070,399),(1.910,.044,.050,.070,378),
      (1.923,.006,.008,.070,367)]
CUT=1.285
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'output/live2d_delta/hunyuan21_polished/Delta_live2d.blend'))
mesh=next(o for o in bpy.data.objects if o.type=='MESH')
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
ownership=np.load(ROOT/'artifacts/live2d/arm_ownership.npy')
head_mask=np.load(ROOT/'artifacts/live2d/head_visible.npy')
neck_mask=np.load(ROOT/'artifacts/live2d/neck_visible.npy')
face_mask=np.load(ROOT/'artifacts/live2d/face_visible.npy')
if CLEAN_FACE:
    padded=np.pad(face_mask,8)
    face_mask=np.maximum.reduce([padded[8+dy:2208+dy,8+dx:1408+dx] for dx,dy in
        [(0,0),(-8,0),(8,0),(0,-8),(0,8),(-6,-6),(6,-6),(-6,6),(6,6)]])
source_rgb=np.load(ROOT/'artifacts/live2d/source_rgb.npy')
groups={g.name:g.index for g in mesh.vertex_groups}
def group(n):
    if n not in groups:groups[n]=mesh.vertex_groups.new(name=n).index
    return groups[n]
def point(n):return mesh.matrix_world.inverted()@(arm.matrix_world@arm.data.bones[n].head_local)
def smooth(t):t=max(0.,min(1.,t));return t*t*(3-2*t)
def sample(a,x,y):return float(a[min(2199,max(0,round(y))),min(1399,max(0,round(x)))])
spines=sorted((point(n).z,n) for n in ['spine_01','spine_02','spine_03','spine_04','spine_05'])
def body_weights(p):
    z,x=p.z,p.x
    base={spines[0][1]:1.}
    for (za,na),(zb,nb) in zip(spines,spines[1:]):
        if z>=za:
            t=smooth((z-za)/(zb-za));base={na:1-t,nb:t}
    if z>=spines[-1][0]:base={spines[-1][1]:1.}
    s=.80*smooth((abs(x)-.055)/.115)*smooth((z-1.43)/.065)
    t=.85*smooth((z-1.55)/.065)*(1-s)
    result={n:w*(1-s-t) for n,w in base.items()}
    result['clavicle_'+('l' if x>=0 else 'r')]=s
    result['neck_01']=t
    return result
bm=bmesh.new();bm.from_mesh(mesh.data)
uv=bm.loops.layers.uv.active;dv=bm.verts.layers.deform.verify()
def pixel(loop):u,v=loop[uv].uv;return float(u*1400),float((1-v)*2200)
# A planar cut gives the retained lower outfit a clean edge. It only splits
# other surfaces; classification below selects the actual removed region.
bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
    plane_co=(0,0,CUT),plane_no=(0,0,1),dist=1e-6)
remove=[];head_verts=set();neck_verts=set();neck_faces=[];ribbon_verts=set()
original_pixels={v:pixel(v.link_loops[0]) for v in bm.verts if v.link_loops}
for f in bm.faces:
    x,y=np.mean([pixel(l) for l in f.loops],axis=0)
    rgb=source_rgb[min(2199,max(0,round(y))),min(1399,max(0,round(x)))]
    if x<550 and 735<y<830 and int(rgb[2])>int(rgb[0])*1.5 and int(rgb[2])>int(rgb[1])*1.2:
        ribbon_verts.update(f.verts);continue
    ishead=y<599 or (y<630 and abs(x-694.5)>48 and sample(head_mask,x,y)>.5)
    if ishead:
        hair_color=int(rgb[2])-int(rgb[0])>4
        if CLEAN_FACE and f.calc_center_median().y<.10 and max(sample(face_mask,*pixel(l)) for l in f.loops)>.05:
            remove.append(f);continue
        if not KEEP_FACE and f.calc_center_median().y<.08 and (sample(face_mask,x,y)>.5 or (y>565 and not hair_color)):
            remove.append(f);continue
        if KEEP_FACE and sample(face_mask,x,y)>.25 and f.calc_center_median().y<.08:
            f.material_index=0
        head_verts.update(f.verts);continue
    isneck=False
    if isneck:
        neck_verts.update(f.verts);neck_faces.append(f);continue
    c=f.calc_center_median()
    isarm=690<y<1080 and abs(x-694.5)>65 and sample(ownership,x,y)>.08
    isupper=c.z>CUT+1e-6
    if isarm or isupper:remove.append(f)
removed=len(remove);bmesh.ops.delete(bm,geom=remove,context='FACES')
boundary=[];seen=set()
for e in bm.edges:
    if len(e.link_faces)!=1 or any(abs(v.co.z-CUT)>.00001 for v in e.verts) or e in seen:continue
    stack=[e];edges=[]
    while stack:
        ee=stack.pop()
        if ee in seen:continue
        seen.add(ee);edges.append(ee)
        for v in ee.verts:
            stack.extend(q for q in v.link_edges if q not in seen and len(q.link_faces)==1 and all(abs(vv.co.z-CUT)<.00001 for vv in q.verts))
    vs=set(v for ee in edges for v in ee.verts)
    boundary.append({'edges':len(edges),'verts':len(vs),'positions':[list(v.co) for v in vs]})
(OUT/'lower_boundary.json').write_text(json.dumps(boundary))
for v in head_verts:
    if not v.is_valid:continue
    v.co.z-=.100
    v.co.y=.050+(v.co.y-.050)*.85
    x,y=original_pixels[v]
    if RELAX_FACE:
        xx,yy,zz=v.co
        influence=smooth((zz-1.61)/.035)*smooth((1.82-zz)/.04)*smooth((.115-abs(xx))/.025)*smooth((.075-yy)/.04)
        rx=float(np.interp(zz,[s[0] for s in HEAD_PROFILE],[s[1] for s in HEAD_PROFILE]))
        ry=float(np.interp(zz,[s[0] for s in HEAD_PROFILE],[s[2] for s in HEAD_PROFILE]))
        cy=float(np.interp(zz,[s[0] for s in HEAD_PROFILE],[s[3] for s in HEAD_PROFILE]))
        target=cy-ry*math.sqrt(max(.02,1-(xx/max(rx,.005))**2))
        target-=.006*math.exp(-(xx/.014)**2-((zz-1.704)/.018)**2)
        v.co.y=yy*(1-influence)+target*influence
    if KEEP_FACE and not ORIGINAL_HEAD and sample(face_mask,x,y)>.5 and v.co.y<.08:
        zz=1.649674+(592-y)*(1.95/1607);xx=(x-694.5)*(1.95/1607)
        rx=float(np.interp(zz,[s[0] for s in HEAD_PROFILE],[s[1] for s in HEAD_PROFILE]))
        ry=float(np.interp(zz,[s[0] for s in HEAD_PROFILE],[s[2] for s in HEAD_PROFILE]))
        cy=float(np.interp(zz,[s[0] for s in HEAD_PROFILE],[s[3] for s in HEAD_PROFILE]))
        v.co=Vector((xx,cy-ry*math.sqrt(max(.02,1-(xx/max(rx,.005))**2))-.0015,zz))
    v[dv].clear();v[dv][group('head')]=1.
for v in ribbon_verts:
    if v.is_valid:
        v[dv].clear();v[dv][group('upperarm_r')]=.9;v[dv][group('clavicle_r')]=.1
for v in neck_verts:
    if not v.is_valid:continue
    x,y=original_pixels[v]
    if y<599:continue
    v.co.z=float(np.interp(y,[599,620,650,675],[1.648,1.625,1.600,1.580]))
    v.co.x=(x-694.5)*.00125
    old_y=.05+(v.co.y-.05)*.85
    t=smooth((y-600)/48.)
    target_y=.018 if old_y<.05 else .082
    v.co.y=old_y*(1-t)+target_y*t
    high=smooth((v.co.z-1.60)/.05)
    v[dv].clear()
    v[dv][group('neck_01')]=1-high
    v[dv][group('head')]=high
for f in neck_faces:
    if not f.is_valid:continue
    f.material_index=6
    for l in f.loops:l[uv].uv=(.99,.01)
closed_head_faces=0
if ORIGINAL_HEAD:
    # The semantic cut crosses several fused fringe strands. Close each actual
    # boundary loop; a fan to one common head center would span unrelated loops.
    edges=[e for e in bm.edges if e.is_boundary and all(v in head_verts for v in e.verts)]
    patches=bmesh.ops.holes_fill(bm,edges=edges,sides=0)['faces']
    patches=bmesh.ops.triangulate(bm,faces=patches)['faces'] if patches else []
    for f in patches:
        c=f.calc_center_median();skin=abs(c.x)<.052 and c.y<.065
        f.material_index=6 if skin else 0;f.smooth=True
        for l in f.loops:l[uv].uv=(.99,.01) if skin else (700/1400,1-400/2200)
    closed_head_faces=len(patches)
# Give the retained hair shell an inner surface behind the new head. Removing
# the fused face otherwise leaves open sheets around the jaw and rear fringe.
hair_boundary=[] if KEEP_FACE or CLEAN_FACE else [e for e in bm.edges if len(e.link_faces)==1 and all(v in head_verts for v in e.verts)]
hair_center=bm.verts.new((0,.07,1.765));hair_center[dv][group('head')]=1.
for e in hair_boundary:
    va,vb=e.verts
    f=bm.faces.new([vb,va,hair_center]);f.material_index=1;f.smooth=True
    for l in f.loops:l[uv].uv=(.5,1-430/2200)
# Bridge the existing jaw edge down to the inner neck, preserving the face
# silhouette. A disk across the whole head also spans the hair, and an added
# ellipsoid can obscure the painted face; neither is an acceptable jaw repair.
inner={};bridged=0
for e in []:
    if len(e.link_faces)!=1 or not all(v in head_verts for v in e.verts):continue
    if not all(v.co.z>1.61 and v.co.y<.09 and abs(v.co.x)<.085 and original_pixels.get(v,(0,0))[1]>570 for v in e.verts):continue
    for v in e.verts:
        if v not in inner:
            angle=math.atan2((v.co.y-.05)/.031,v.co.x/.035)
            q=bm.verts.new((.035*math.cos(angle),.05+.031*math.sin(angle),1.651))
            q[dv][group('head')]=1.;inner[v]=q
    va,vb=e.verts
    f=bm.faces.new([va,vb,inner[vb],inner[va]]);f.smooth=True;f.material_index=6
    for l in f.loops:l[uv].uv=(.99,.01)
    bridged+=1
# Bring the retained outfit's cut edge onto the same body contour and blend
# the deformation field too, rather than leaving a ledge across the chest.
for v in bm.verts:
    if v in head_verts or v in neck_verts or not v.link_faces or not CUT-.055<v.co.z<CUT+.00001:continue
    if abs(v.co.x)>.19:continue
    t=smooth((v.co.z-(CUT-.055))/.055)
    a=math.atan2((v.co.y-.005)/.105,v.co.x/.166)
    target=Vector((.166*math.cos(a),.005+.105*math.sin(a),v.co.z))
    v.co=v.co.lerp(target,t)
    previous=dict(v[dv]);v[dv].clear()
    combined={n:w*t for n,w in body_weights(v.co).items()}
    for index,value in previous.items():
        name=mesh.vertex_groups[index].name;combined[name]=combined.get(name,0.)+value*(1-t)
    for name,value in combined.items():
        if value>1e-6:v[dv][group(name)]=value
# Eliminate orphan vertices so no old shoulder weights survive invisibly.
orphans=[v for v in bm.verts if not v.link_faces]
bmesh.ops.delete(bm,geom=orphans,context='VERTS')
bm.to_mesh(mesh.data);bm.free();mesh.data.update()

# A closed construction mesh is fused before any UV or weights are assigned.
g=bmesh.new();guv=g.loops.layers.uv.new('Live2DFrontProjection');gd=g.verts.layers.deform.verify()
def assign(v,weights):
    total=sum(weights.values())
    for n,w in weights.items():
        if w>1e-7:v[gd][group(n)]=w/total
def face(verts,pixels,mat=0):
    f=g.faces.new(verts);f.smooth=True;f.material_index=mat
    for l,p in zip(f.loops,pixels):l[guv].uv=(p[0]/1400,1-p[1]/2200)
    return f
def loft(specs,n=48,neck=False):
    rings=[];uvs=[]
    for z,rx,ry,cy,sy in specs:
        r=[];ruv=[]
        for j in range(n):
            a=2*math.pi*j/n;x=rx*math.cos(a);y=cy+ry*math.sin(a)
            if not neck:
                bust=.018*math.exp(-((z-1.455)/.065)**2)*(math.exp(-((x-.070)/.060)**2)+math.exp(-((x+.070)/.060)**2))
                y-=bust*max(0.,-math.sin(a))**4
            v=g.verts.new((x,y,z));r.append(v)
            if neck:
                t=smooth((z-1.600)/.050)
                assign(v,{'head':1.} if neck=='head' else {'neck_01':1-t,'head':t})
                ruv.append((694.5+x/(1.95/1607),592-(z-1.649674)/(1.95/1607)) if neck=='head' else (1386,2178))
            else:
                assign(v,body_weights(v.co))
                ruv.append((694.5+x/.00143,sy))
        if rings:
            for j in range(n):
                jj=(j+1)%n
                material=(6 if z<1.668 else 0 if math.sin(2*math.pi*(j+.5)/n)<0 else 1) if neck=='head' else 6 if neck else (0 if math.sin(2*math.pi*(j+.5)/n)<0 else 2)
                face([rings[-1][j],rings[-1][jj],r[jj],r[j]],
                     [uvs[-1][j],uvs[-1][jj],ruv[jj],ruv[j]],
                     material)
        rings.append(r);uvs.append(ruv)
    for i in [0,-1]:face(rings[i],uvs[i],1 if neck=='head' else 6 if neck else 2)
    return rings

yoke=[(1.255,.157,.098,.005,937),(1.275,.164,.104,.005,916),(1.285,.166,.105,.005,905),
      (1.30,.162,.107,.003,889),(1.33,.165,.112,-.002,856),(1.37,.174,.120,-.006,829),
      (1.40,.180,.125,-.006,810),(1.43,.186,.125,-.006,788),(1.46,.190,.119,-.004,765),
      (1.49,.180,.108,.002,740),(1.51,.182,.097,.012,722)]
if ANATOMICAL:
    yoke += [(1.529,.181,.083,.026,714),(1.537,.158,.073,.032,704),
      (1.545,.126,.064,.038,687),(1.553,.103,.054,.041,672),
      (1.561,.080,.044,.044,663),(1.573,.057,.037,.046,655),
      (1.586,.039,.032,.047,650)]
else:
    yoke += [
      (1.529,.181,.083,.026,690),(1.537,.158,.073,.032,675),
      (1.545,.126,.064,.038,662),(1.553,.103,.054,.041,651),
      (1.569,.080,.044,.044,638),(1.592,.057,.037,.046,626),
      (1.615,.039,.032,.047,618)]
loft(yoke)
if ANATOMICAL:
    loft([(1.548,.048,.040,.047,680),(1.566,.042,.037,.047,667),
      (1.584,.037,.034,.047,650),(1.602,.032,.031,.047,635),
      (1.620,.031,.030,.048,625),(1.640,.032,.030,.049,615),
      (1.660,.034,.031,.049,605),(1.682,.038,.034,.050,600)],32,True)
else:loft([(1.580,.038,.033,.047,640),(1.605,.035,.031,.047,630),
      (1.630,.033,.030,.048,620),(1.655,.034,.031,.049,610),
      (1.682,.038,.034,.050,600)],32,True)
if not ORIGINAL_HEAD:loft(HEAD_PROFILE,64,'head')
arm_info={}
for side,sign in [('l',1),('r',-1)]:
    a,e,w=[point(n+'_'+side) for n in ['upperarm','lowerarm','hand']]
    a.x-=sign*.020;e.x-=sign*.020
    d=(e-a).normalized();fd=(w-e).normalized();u=(e-a).length;fore=(w-e).length;length=u+fore
    stations=sorted(set([-.07,-.05,-.035,-.018,0.,.014,.028,.045,.065,.09,.12,.16,.20,
        u-.06,u-.04,u-.025,u-.012,u,u+.012,u+.025,u+.04,u+.06,
        u+fore*.30,u+fore*.40,u+fore*.46,u+fore*.48,u+fore*.52,
        u+fore*.62,u+fore*.72,u+fore*.82,u+fore*.90,u+fore*.97,length,length+.008]))
    radii=sorted([(-.07,.026),(-.05,.037),(-.018,.045),(0.,.047),(.045,.046),(.12,.041),
        (u-.05,.035),(u,.032),(u+.035,.034),(u+fore*.30,.038),
        (u+fore*.46,.040),(u+fore*.48,.039),(u+fore*.52,.0285),
        (u+fore*.72,.027),(u+fore*.90,.0245),(length+.008,.0235)])
    rings=[];uvs=[]
    for s in stations:
        if s<=u:
            t=s/u;c=a+(e-a)*t;sx=694.5+sign*(136+84*t);sy=720+155*t
        else:
            t=(s-u)/fore;c=e+(w-e)*t;sx=694.5+sign*(220+90*t);sy=875+165*t
        blend=smooth((s-u+.035)/.07);tangent=(d*(1-blend)+fd*blend).normalized()
        back=Vector((0,1,0));back=(back-tangent*back.dot(tangent)).normalized()
        up=tangent.cross(back).normalized()*sign
        radius=float(np.interp(s,[p[0] for p in radii],[p[1] for p in radii]))
        elbow=smooth((s-u+.040)/.080);clav=.70*smooth((.06-s)/.12)
        weights={'upperarm_'+side:(1-elbow)*(1-clav),'clavicle_'+side:(1-elbow)*clav,'lowerarm_'+side:elbow}
        twist=.65*smooth((s-u-.035)/.15)
        weights['lowerarm_twist_01_'+side]=weights['lowerarm_'+side]*twist;weights['lowerarm_'+side]*=1-twist
        wrist=.5*smooth((s-length+.04)/.05)
        weights={n:v*(1-wrist) for n,v in weights.items()};weights['hand_'+side]=wrist
        r=[];ruv=[]
        for j in range(32):
            angle=2*math.pi*j/32;radial=up*math.cos(angle)+back*math.sin(angle)
            v=g.verts.new(c+radial*radius);assign(v,weights);r.append(v)
            half=25. if sy<880 else 27. if sy<950 else 13.
            dx,dy=(84.,155.) if sy<875 else (90.,165.);norm=math.hypot(dx,dy)
            ruv.append((sx+sign*dy/norm*half*math.cos(angle),sy-dx/norm*half*math.cos(angle)))
        if rings:
            for j in range(32):
                jj=(j+1)%32
                verts=[rings[-1][j],rings[-1][jj],r[jj],r[j]]
                pixels=[uvs[-1][j],uvs[-1][jj],ruv[jj],ruv[j]]
                mat=0 if math.sin(2*math.pi*(j+.5)/32)<0 else 2
                mid_s=(s+stations[len(rings)-1])*.5
                if mid_s>u+fore*.52:
                    if mid_s>u+fore*.85 and mid_s<u+fore*.97:
                        mat=2;pixels=[(694.5,850.)]*4
                    else:mat=6;pixels=[(1386.,2178.)]*4
                elif mat==2:
                    if mid_s>u+fore*.43:
                        mat=0;pixels=[(939.,943.)]*4
                    else:pixels=[(694.5,850.)]*4
                face(verts,pixels,mat)
        rings.append(r);uvs.append(ruv)
    for i in [0,-1]:face(rings[i],uvs[i],2)
    arm_info[side]={'upper_m':u,'forearm_m':fore,'ratio':u/fore}

bmesh.ops.recalc_face_normals(g,faces=list(g.faces));bmesh.ops.triangulate(g,faces=list(g.faces))
g.verts.ensure_lookup_table();g.faces.ensure_lookup_table()
g.verts.index_update();g.faces.index_update()
assert all(v.index==i for i,v in enumerate(g.verts))
donor_coords=[v.co.copy() for v in g.verts]
donor_faces=[[v.index for v in f.verts] for f in g.faces]
donor_uv=[[Vector((*l[guv].uv,0.)) for l in f.loops] for f in g.faces]
donor_weights=[dict(v[gd]) for v in g.verts];donor_mats=[f.material_index for f in g.faces]
tree=BVHTree.FromPolygons(donor_coords,donor_faces,all_triangles=True)
material_faces={m:[i for i,value in enumerate(donor_mats) if value==m] for m in set(donor_mats)}
material_trees={m:BVHTree.FromPolygons(donor_coords,[donor_faces[i] for i in ids],all_triangles=True) for m,ids in material_faces.items()}
data=bpy.data.meshes.new('Continuous upper body');g.to_mesh(data);g.free()
upper=bpy.data.objects.new('Continuous upper body',data);bpy.context.collection.objects.link(upper)
for m in mesh.data.materials:upper.data.materials.append(m)
for name,index in sorted(groups.items(),key=lambda p:p[1]):upper.vertex_groups.new(name=name)
bpy.ops.object.select_all(action='DESELECT');upper.select_set(True);bpy.context.view_layer.objects.active=upper
upper.data.remesh_voxel_size=.004;upper.data.remesh_voxel_adaptivity=0.
bpy.ops.object.voxel_remesh()
mod=upper.modifiers.new('Round shoulder union','SMOOTH');mod.factor=.40;mod.iterations=4
bpy.ops.object.modifier_apply(modifier=mod.name)
upper.vertex_groups.clear()
for name,index in sorted(groups.items(),key=lambda p:p[1]):
    created=upper.vertex_groups.new(name=name)
    assert created.index==index
layer=upper.data.uv_layers.get('Live2DFrontProjection') or upper.data.uv_layers.new(name='Live2DFrontProjection')
# Interpolate the construction surface's UV and weights after fusion.
nearest=[]
for v in upper.data.vertices:
    hit,normal,fi,distance=tree.find_nearest(v.co);nearest.append((hit,fi))
    ids=donor_faces[fi];abc=[donor_coords[i] for i in ids]
    bary=barycentric_transform(hit,*abc,Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))
    weights={}
    for i,k in zip(ids,bary):
        for group_index,value in donor_weights[i].items():weights[group_index]=weights.get(group_index,0.)+max(0.,k)*value
    total=sum(weights.values())
    for group_index,value in weights.items():
        if value>1e-6:upper.vertex_groups[group_index].add([v.index],value/total,'REPLACE')
for p in upper.data.polygons:
    p.use_smooth=True
    _,_,fi,_=tree.find_nearest(p.center);p.material_index=donor_mats[fi]
    # Project each corner onto its local construction face. Extrapolating all
    # corners on the center's tiny triangle produced repeated cuff bands.
    for li in p.loop_indices:
        vi=upper.data.loops[li].vertex_index
        hit,_,local_fi,_=material_trees[p.material_index].find_nearest(upper.data.vertices[vi].co)
        corner_fi=material_faces[p.material_index][local_fi]
        ids=donor_faces[corner_fi];abc=[donor_coords[i] for i in ids]
        layer.data[li].uv=(.99,.01) if p.material_index==6 else barycentric_transform(hit,*abc,*donor_uv[corner_fi]).xy
weight_sums=[sum(g.weight for g in v.groups) for v in upper.data.vertices]
assert min(weight_sums)>.999 and max(weight_sums)<1.001,(min(weight_sums),max(weight_sums))

# The shirt collar and coat lapels are thin fabric over the volume, rather
# than the same neck cone. Their source coordinates retain the actual design.
bm=bmesh.new();bm.from_mesh(upper.data);uv=bm.loops.layers.uv.active;dv=bm.verts.layers.deform.verify()
zsy=([(600,1.610),(620,1.588),(650,1.562),(680,1.536),(710,1.506),(750,1.468),(790,1.420),(825,1.375)] if ANATOMICAL else
     [(600,1.648),(620,1.618),(650,1.581),(680,1.550),(710,1.514),(750,1.468),(790,1.420),(825,1.375)])
def panel_point(px,py,offset=.006):
    z=float(np.interp(py,[p[0] for p in zsy],[p[1] for p in zsy]));x=(px-694.5)*.00143
    z-=.030*smooth((abs(x)-.055)/.12)
    # Front ellipse lookup via a ray; collar corners can extend outside it.
    hit,normal,fi,dist=tree.find_nearest(Vector((x,-.16,z)))
    y=hit.y-offset
    return Vector((x,y,z))
def panel(points,side):
    # Subdivide source polygon triangles for a panel that follows the chest.
    panel_bm=bmesh.new();panel_uv=panel_bm.loops.layers.uv.new('Live2DFrontProjection');panel_deform=panel_bm.verts.layers.deform.verify()
    vertices=[panel_bm.verts.new(panel_point(x,y)) for x,y in points]
    f=panel_bm.faces.new(vertices);f.material_index=0;f.smooth=True
    for l,(x,y) in zip(f.loops,points):l[panel_uv].uv=(x/1400,1-y/2200)
    result=bmesh.ops.triangulate(panel_bm,faces=[f])
    edges=list(set(e for q in result['faces'] for e in q.edges))
    bmesh.ops.subdivide_edges(panel_bm,edges=edges,cuts=5,use_grid_fill=True)
    for v in panel_bm.verts:
        hit,_,_,_=tree.ray_cast(Vector((v.co.x,-.5,v.co.z)),Vector((0,1,0)))
        if hit is not None:v.co.y=hit.y-.004
        for name,value in body_weights(v.co).items():
            if value>1e-6:v[panel_deform][group(name)]=value
    # Give lapels a real fabric thickness and an underside.
    bmesh.ops.solidify(panel_bm,geom=list(panel_bm.faces),thickness=.002)
    panel_data=bpy.data.meshes.new('Panel temporary');panel_bm.to_mesh(panel_data);panel_bm.free()
    bm.from_mesh(panel_data);bpy.data.meshes.remove(panel_data)
for sign,side in [(1,'l'),(-1,'r')]:
    # Raised outer collar and folded notch/lapel; sampled from Delta itself.
    if not FLAT_COLLAR:panel([(694.5+sign*x,y) for x,y in [(30,610),(126,653),(87,702),(53,688),(26,645)]],side)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(upper.data);bm.free();upper.data.update()
tag=upper.data.attributes.new('rebuild_origin','INT','FACE')
for entry in tag.data:entry.value=1

bpy.ops.object.select_all(action='DESELECT');upper.select_set(True);mesh.select_set(True);bpy.context.view_layer.objects.active=mesh
bpy.ops.object.join()
mesh['upper_body_rebuild']='continuous voxel union, corrected head anchor, separate garment collar'
mesh['limits']='Offline work in progress; visual acceptance is not implied'
sys.path.insert(0,str(ROOT/'scripts'))
from delta_surface_normals import soften_face_normals
soften_face_normals(mesh)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Delta_live2d.blend'))
report={'method':'continuous shoulder/neck/sleeve surface with separate collar','head_translation_m':-.100,
        'removed_old_faces':removed,'jaw_bridge_faces':bridged,'vertices':len(mesh.data.vertices),'arms':arm_info,'accepted':False,
        'anatomical_neck':ANATOMICAL,'garment_neckline_z_m':1.586 if ANATOMICAL else 1.615,'face_shell_preserved':KEEP_FACE,
        'original_head_geometry_preserved':ORIGINAL_HEAD,'closed_head_boundary_faces':closed_head_faces,
        'clean_face':CLEAN_FACE,'flat_collar':FLAT_COLLAR,'relax_face':RELAX_FACE}
(OUT/'shoulder_rebuild.json').write_text(json.dumps(report,indent=2))
print('UPPER_BODY_REBUILT',json.dumps(report))
