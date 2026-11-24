"""Assemble source BaiQi clothing and accessories on the female foundation.

This is an editable native-rig WIP, not a cooked or accepted Mod. Unseen backs
and thickness are authored geometry; the source only specifies the front.
"""
import argparse,json,math,sys
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--head',default='output/live2d_delta/baiqi_head_surface_007');p.add_argument('--output',default='output/live2d_delta/baiqi_full_assembly_006');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);OUT=ROOT/a.output;OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/a.head/'BaiQi_Assembly.blend'))
base=bpy.data.objects['BaiQi_FemaleFoundation'];arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
source=json.loads((ROOT/'repro/baiqi_source/core_geometry.json').read_text(encoding='utf-8'));parts={p['id']:p for p in source['parts']};cols={k:next(c for c in bpy.data.collections if c.name=='BaiQi '+k+' '+v['source_name']) for k,v in parts.items()}
records=json.loads((ROOT/a.head/'assembly_report.json').read_text(encoding='utf-8'))['objects'];SCALE=195/1607;LAYER=ROOT/'artifacts/baiqi_component_audit/body_layers'
def desc(part):
    ids={part}
    for c in parts[part]['children']:ids.update(desc(c))
    return ids
def uv_canvas(x,z):return ((x/SCALE+694.5)/1400,1-(600-(z-165.35)/SCALE)/2200)
def pixel_cm(px,py):return ((px-694.5)*SCALE,165.35+(600-py)*SCALE)
def material(name,color,layer=None,alpha=False):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.surface_render_method='DITHERED';n=m.node_tree.nodes;l=m.node_tree.links;b=n['Principled BSDF'];b.inputs['Base Color'].default_value=(*color,1);b.inputs['Roughness'].default_value=.85
    if layer:
        im=bpy.data.images.load(str(LAYER/(layer+'.png')),check_existing=True);im.pack();t=n.new('ShaderNodeTexImage');t.image=im;t.extension='CLIP';uv=n.new('ShaderNodeUVMap');uv.uv_map='BaiQiCanvas';l.new(uv.outputs['UV'],t.inputs['Vector'])
        if alpha:l.new(t.outputs['Color'],b.inputs['Base Color']);l.new(t.outputs['Alpha'],b.inputs['Alpha'])
        else:
            mix=n.new('ShaderNodeMixRGB');mix.inputs[1].default_value=(*color,1);l.new(t.outputs['Color'],mix.inputs[2]);l.new(t.outputs['Alpha'],mix.inputs[0]);l.new(mix.outputs[0],b.inputs['Base Color'])
    return m
cloth=(.058,.050,.080);white=(.78,.80,.84);gold=(.85,.59,.035);blue=(.017,.037,.14)
shirtmat=material('BaiQi white blouse',white,'shirt');sleeve_l=material('BaiQi sleeve screen right',cloth,'sleeve_screen_right');sleeve_r=material('BaiQi sleeve screen left',cloth,'sleeve_screen_left')
skirtmat=material('BaiQi pleated skirt appearance',white,'skirt');stockmat=material('BaiQi charcoal stockings',(.038,.04,.044),'legs');bootmat=material('BaiQi blue white boots',blue,'shoes');goldmat=material('BaiQi garment gold',gold)
def uv_object(obj,mapper=uv_canvas):
    uv=obj.data.uv_layers.get('BaiQiCanvas') or obj.data.uv_layers.new(name='BaiQiCanvas')
    for loop in obj.data.loops:
        co=obj.data.vertices[loop.vertex_index].co;uv.data[loop.index].uv=mapper(co.x,co.z)
    obj.data.uv_layers.active=uv
def rigid(obj,bone):
    obj.vertex_groups.clear();obj.vertex_groups.new(name=bone).add(list(range(len(obj.data.vertices))),1,'REPLACE')
def register(obj,part,contributors,method='source appearance on three-dimensional garment',preserve_weights=False,bone=None):
    for c in list(obj.users_collection):c.objects.unlink(obj)
    cols[part].objects.link(obj);obj.parent=arm;obj.modifiers.clear()
    if bone:rigid(obj,bone)
    if not preserve_weights and not bone:
        obj.vertex_groups.clear();groups={n:obj.vertex_groups.new(name=n) for n in ['pelvis','spine_01','spine_03','spine_05','neck_01']}
        for v in obj.data.vertices:
            z=v.co.z;knots=[100,113,128,143,158,166];rows=np.array([[1,0,0,0,0],[.6,.4,0,0,0],[0,.4,.6,0,0],[0,0,.4,.6,0],[0,0,0,.8,.2],[0,0,0,0,1]])
            for i,n in enumerate(groups):
                w=float(np.interp(z,knots,rows[:,i]))
                if w>1e-6:groups[n].add([v.index],w,'REPLACE')
    m=obj.modifiers.new('Native adult linear skin','ARMATURE');m.object=arm;m.use_deform_preserve_volume=False
    for f in obj.data.polygons:f.use_smooth=True
    obj['baiqi_source_parts']=json.dumps(sorted(contributors));obj['migration_status']='assembled_pending_review';records.append({'object':obj.name,'source_parts':sorted(contributors),'method':method})
def subset(obj,name,keep):
    duplicate=obj.copy();duplicate.data=obj.data.copy();duplicate.name=name;bpy.context.scene.collection.objects.link(duplicate)
    bm=bmesh.new();bm.from_mesh(duplicate.data);bmesh.ops.delete(bm,geom=[f for f in bm.faces if not keep(f,bm)],context='FACES');bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS');bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.001);bm.to_mesh(duplicate.data);bm.free();duplicate.data.materials.clear();return duplicate
# Authored CC0 blouse, skirt and shoes, fitted in the same native rest space.
with bpy.data.libraries.load(str(ROOT/'output/live2d_delta/anatomy_foundation_004/Delta_adult.blend'),link=False) as (src,dst):dst.objects=['AnatomicalFoundation_WIP']
garments=dst.objects[0];bpy.context.scene.collection.objects.link(garments)
def garment_class(index):return lambda f,bm:f[bm.faces.layers.int['anatomy_source_object']]==0 and f[bm.faces.layers.int['anatomy_source_material']]==index
torso_ids={base.vertex_groups[n].index for n in ['pelvis','spine_01','spine_03','spine_05','neck_01','neck_02']}
def torso_face(f,bm):
    tag=bm.faces.layers.int['anatomy_source_object'];mat=bm.faces.layers.int['anatomy_source_material'];deform=bm.verts.layers.deform.active
    return f[tag]==0 and f[mat]==0 and all(127<v.co.z<160 for v in f.verts) and sum(sum(v[deform].get(i,0) for i in torso_ids) for v in f.verts)/len(f.verts)>.65
shirt=subset(base,'BaiQi fitted white blouse',torso_face)
for v in shirt.data.vertices:
    v.co.x*=1.025;v.co.y=5+(v.co.y-5)*1.045
shirt.data.materials.append(shirtmat);uv_object(shirt);register(shirt,'Shirt',desc('Shirt')-desc('Part26'),preserve_weights=True)
skirt=subset(garments,'BaiQi pleated skirt',garment_class(3));zs=[v.co.z for v in skirt.data.vertices];lo,hi=min(zs),max(zs)
for v in skirt.data.vertices:v.co.z=94+(v.co.z-lo)/(hi-lo)*32
skirt.data.materials.append(skirtmat);uv_object(skirt);register(skirt,'Skirt',{'Skirt'},preserve_weights=True)
def shoe_uv(x,z):
    sign=1 if x>0 else -1;foot=arm.data.bones['foot_'+('l' if sign>0 else 'r')].head_local
    return uv_canvas(x-foot.x+sign*11.7,z)
shoes=subset(garments,'BaiQi boot foundation',garment_class(4));shoes.data.materials.append(bootmat);uv_object(shoes,shoe_uv);register(shoes,'Leg',{'Part41','Part42','Part43','Part44'},preserve_weights=True)
def foot_surface(f,bm):
    return f[bm.faces.layers.int['anatomy_source_object']]==0 and f[bm.faces.layers.int['anatomy_source_material']]==0 and max(v.co.z for v in f.verts)<29
boot_upper=subset(base,'BaiQi fitted boot upper',foot_surface)
for v in boot_upper.data.vertices:
    foot=arm.data.bones['foot_'+('l' if v.co.x>0 else 'r')].head_local
    v.co.x=foot.x+(v.co.x-foot.x)*1.10;v.co.y=foot.y+(v.co.y-foot.y)*1.10;v.co.z+=.16
boot_upper.data.materials.append(bootmat);boot_upper.data.materials.append(material('BaiQi inferred boot back',blue));uv_object(boot_upper,shoe_uv)
for poly in boot_upper.data.polygons:
    if poly.normal.y>.2:poly.material_index=1
register(boot_upper,'Leg',{'Part41','Part42','Part43','Part44'},'boot upper fitted to authored ankle and foot anatomy',preserve_weights=True)
rearboot=material('BaiQi blue boot heel',blue)
for obj in [shoes,boot_upper]:
    obj.data.materials.append(rearboot);uv=obj.data.uv_layers['BaiQiCanvas']
    for poly in obj.data.polygons:
        if poly.normal.y>.3:poly.material_index=len(obj.data.materials)-1
    for loop in obj.data.loops:
        co=obj.data.vertices[loop.vertex_index].co;side='l' if co.x>0 else 'r';sign=1 if co.x>0 else -1;foot=arm.data.bones['foot_'+side].head_local;ball=arm.data.bones['ball_'+side].head_local;axis=ball-foot;axis.z=0;axis.normalize();lateral=Vector((-axis.y,axis.x,0));along=(co-foot).dot(axis)
        py=1850+float(np.clip((along+7)/21,0,1))*96 if co.z<foot.z else 600-(co.z-165.35)/SCALE
        px=694.5+sign*11.7/SCALE+(co-foot).dot(lateral)/SCALE
        uv.data[loop.index].uv=(px/1400,1-py/2200)
bpy.data.objects.remove(garments,do_unlink=True)
# Stocking colour follows the original anatomical legs, retaining knees and
# calf/ankle forms. It does not replace the leg with cylinders.
base.data.materials.append(stockmat);tag=base.data.attributes['anatomy_source_object'];mat_tag=base.data.attributes['anatomy_source_material']
for poly in base.data.polygons:
    if tag.data[poly.index].value==0 and mat_tag.data[poly.index].value==0 and poly.center.z<90 and poly.center.z>12:poly.material_index=len(base.data.materials)-1
records.append({'object':base.name,'source_parts':['Body','Leg2','Neck','Part31','Part35','Part32','Part36'],'method':'female anatomical skin, hands and stocking appearance; alternate hand poses pending'})
coords=[v.co.copy() for v in base.data.vertices];body_faces=[list(p.vertices) for p in base.data.polygons if tag.data[p.index].value==0 and mat_tag.data[p.index].value==0];tree=BVHTree.FromPolygons(coords,body_faces)
profile=np.array([(98,27,18,5),(110,24,17,5),(125,19,14,5),(135,20,15,4),(145,23,16,5),(152,25,13,5),(158,17,11,5),(164,8,7,5)])
def coat_depth(x,z):
    rx,ry,cy=[np.interp(z,profile[:,0],profile[:,i]) for i in [1,2,3]];y=cy-ry*math.sqrt(max(.02,1-(x/rx)**2))
    hit=tree.ray_cast(Vector((x,-100,z)),Vector((0,1,0)),300)[0]
    if hit and z>118:y=min(y,hit.y-1.8)
    if z>159 and abs(x)<5:y=12
    return y
def source_grid(name,layer,part,contributors,depth,mapper=None,bone=None,step=3):
    im=bpy.data.images.load(str(LAYER/(layer+'.png')),check_existing=True);arr=np.empty(len(im.pixels),dtype=np.float32);im.pixels.foreach_get(arr);mask=arr.reshape(im.size[1],im.size[0],4)[::-1,:,3]>.15;ys,xs=np.nonzero(mask)
    if not len(xs):return None
    vertices=[];faces=[];uvs=[];lookup={}
    def vert(px,py):
        if (px,py) not in lookup:
            x,z=pixel_cm(px,py);co=(x,depth(x,z),z)
            if mapper:co=mapper(co)
            lookup[(px,py)]=len(vertices);vertices.append(co);uvs.append((px/1400,1-py/2200))
        return lookup[(px,py)]
    for py in range(max(0,int(ys.min())-step),min(2200-step,int(ys.max())+step),step):
        for px in range(max(0,int(xs.min())-step),min(1400-step,int(xs.max())+step),step):
            if mask[py:py+step+1,px:px+step+1].any():faces.append([vert(px,py),vert(px,py+step),vert(px+step,py+step),vert(px+step,py)])
    data=bpy.data.meshes.new(name);data.from_pydata(vertices,[],faces);data.materials.append(material(name+' original appearance',(1,1,1),layer,True));uv=data.uv_layers.new(name='BaiQiCanvas')
    for loop in data.loops:uv.data[loop.index].uv=uvs[loop.vertex_index]
    obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj);register(obj,part,contributors,bone=bone);m=obj.modifiers.new('Garment thickness cm','SOLIDIFY');m.thickness=.16;return obj
source_grid('BaiQi open coat front and lapels','coat','Coat',desc('Coat'),coat_depth)
# Side and rear coat panels form a continuous curved garment volume.
coat_image=bpy.data.images.load(str(LAYER/'coat.png'),check_existing=True);arr=np.empty(len(coat_image.pixels),dtype=np.float32);coat_image.pixels.foreach_get(arr);coat_mask=arr.reshape(2200,1400,4)[::-1,:,3]>.5
torso_faces=[]
arm_groups={base.vertex_groups[n+'_'+s].index for n in ['upperarm','lowerarm','hand'] for s in ['l','r']}
for poly in base.data.polygons:
    if tag.data[poly.index].value!=0 or mat_tag.data[poly.index].value!=0:continue
    if max(sum(g.weight for g in base.data.vertices[i].groups if g.group in arm_groups) for i in poly.vertices)<.65:torso_faces.append(list(poly.vertices))
torso_tree=BVHTree.FromPolygons(coords,torso_faces)
verts=[];faces=[];nu=72;nz=80
for z in np.linspace(99,162,nz):
    py=int(np.clip(600-(z-165.35)/SCALE,0,2199));xs=np.flatnonzero(coat_mask[py]);left,right=(pixel_cm(xs[0],py)[0],pixel_cm(xs[-1],py)[0]) if len(xs)>1 else (-9,9);rx=(right-left)/2;cx=(right+left)/2
    centre=Vector((0,5,z));prx,pry,pcy=[np.interp(z,profile[:,0],profile[:,i]) for i in [1,2,3]]
    for j,theta in enumerate(np.linspace(0,math.pi,nu)):
        direction=Vector((math.cos(theta),math.sin(theta),0));hit=torso_tree.ray_cast(centre+direction*100,-direction,160)[0]
        body_radius=(hit-centre).dot(direction)+1.7 if hit else 0
        loose_radius=1/math.sqrt((direction.x/prx)**2+(direction.y/pry)**2)
        t=float(np.clip((z-125)/16,0,1));radius=max(body_radius,loose_radius*(1-.1*t*t*(3-2*t)))
        point=centre+direction*radius
        verts.append(point)
    # A separate edge strip connects source-designed front panels to the
    # anatomical back envelope. Do not pull the back rings into the artwork.
for i in range(nz-1):
    for j in range(nu-1):k=i*nu+j;faces.append((k,k+1,k+1+nu,k+nu))
data=bpy.data.meshes.new('BaiQi coat side back');data.from_pydata(verts,[],faces);data.materials.append(material('BaiQi inferred rear coat',cloth));obj=bpy.data.objects.new('BaiQi coat side back',data);bpy.context.scene.collection.objects.link(obj);register(obj,'Coat',{'Coat'},'authored side and back matching source garment; review required');m=obj.modifiers.new('Coat cloth thickness','SOLIDIFY');m.thickness=.22
for side in [-1,1]:
    v=[];f=[]
    for i,z in enumerate(np.linspace(99,162,nz)):
        py=int(np.clip(600-(z-165.35)/SCALE,0,2199));xs=np.flatnonzero(coat_mask[py]);edge=pixel_cm(xs[0] if side<0 else xs[-1],py)[0] if len(xs) else side*9
        v.extend([(edge,coat_depth(edge,z)+.12,z),verts[i*nu+(nu-1 if side<0 else 0)]])
    for i in range(nz-1):f.append((2*i,2*i+1,2*i+3,2*i+2))
    data=bpy.data.meshes.new('BaiQi coat side seam '+str(side));data.from_pydata(v,[],f);data.materials.append(material('BaiQi coat seam pigment '+str(side),cloth));obj=bpy.data.objects.new(data.name,data);bpy.context.scene.collection.objects.link(obj);register(obj,'Coat',{'Coat'})
# Corset follows chest/waist depth rather than an image plate.
def girdle_depth(x,z):
    hit=tree.ray_cast(Vector((x,-100,z)),Vector((0,1,0)),300)[0]
    return (hit.y-2.5 if hit else -8)
source_grid('BaiQi navy gold laced girdle','girdle','Part29',desc('Part29'),girdle_depth)
source_grid('BaiQi black gold bow tie','bow_tie','Part26',desc('Part26'),lambda x,z:girdle_depth(x,z)-1,bone='spine_05',step=2)
# Sleeves retain anatomical elbow geometry and original native skin weights.
for side,mat in [('l',sleeve_l),('r',sleeve_r)]:
    groupids={base.vertex_groups[n+'_'+side].index for n in ['upperarm','lowerarm']};w=arm.data.bones['hand_'+side].head_local;e=arm.data.bones['lowerarm_'+side].head_local;shoulder=arm.data.bones['upperarm_'+side].head_local;axis=(w-e).normalized();length=(w-e).length
    def keep(f,bm):
        deform=bm.verts.layers.deform.active
        return all(sum(v[deform].get(i,0) for i in groupids)>.25 for v in f.verts) and sum((v.co-e).dot(axis)/length for v in f.verts)/len(f.verts)<.66
    sleeve=subset(base,'BaiQi anatomical sleeve '+side,keep);sleeve.data.materials.append(mat)
    for v in sleeve.data.vertices:
        t=float(np.clip((v.co-shoulder).dot((e-shoulder).normalized())/(e-shoulder).length,0,1));centre=shoulder.lerp(e,t)
        if (v.co-e).dot(axis)>0:centre=e+axis*float(np.clip((v.co-e).dot(axis),0,length))
        radial=v.co-centre;v.co=centre+radial*1.17
    uv=sleeve.data.uv_layers.get('BaiQiCanvas')
    sign=1 if side=='l' else -1
    sa=np.array(pixel_cm(831 if sign>0 else 558,686));se=np.array(pixel_cm(915 if sign>0 else 474,880));sw=np.array(pixel_cm(970 if sign>0 else 419,1030))
    for loop in sleeve.data.loops:
        co=sleeve.data.vertices[loop.vertex_index].co;aa,bb,cc,dd=(shoulder,e,sa,se) if (co-e).dot(axis)<0 else (e,w,se,sw)
        va=np.array([aa.x,aa.z]);vb=np.array([bb.x,bb.z]);direction=(vb-va)/np.linalg.norm(vb-va);delta=np.array([co.x,co.z])-va;sd=(dd-cc)/np.linalg.norm(dd-cc);q=cc+sd*np.dot(delta,direction)*np.linalg.norm(dd-cc)/np.linalg.norm(vb-va)+np.array([-sd[1],sd[0]])*np.dot(delta,[-direction[1],direction[0]])*.85;uv.data[loop.index].uv=uv_canvas(*q)
    register(sleeve,'Part39' if side=='l' else 'Part38',{'Part39','Sleeve2'} if side=='l' else {'Part38','Sleeve'},preserve_weights=True)
    # The black wrist band is a separate fitted accessory at the actual wrist.
    def band(name,centre,width,radius,mat,part,bone):
        n=axis;u=n.cross(Vector((0,1,0))).normalized();v=n.cross(u).normalized();vs=[];fs=[]
        for along in [-width/2,width/2]:
            for j in range(40):theta=2*math.pi*j/40;vs.append(centre+n*along+radius*(u*math.cos(theta)+v*math.sin(theta)))
        for j in range(40):fs.append((j,(j+1)%40,(j+1)%40+40,j+40))
        d=bpy.data.meshes.new(name);d.from_pydata(vs,[],fs);d.materials.append(mat);o=bpy.data.objects.new(name,d);bpy.context.scene.collection.objects.link(o);register(o,part,{part},bone=bone);m=o.modifiers.new('Band thickness','SOLIDIFY');m.thickness=.3;return o
    band('BaiQi wrist band '+side,w-axis*1,2.9,2.4,material('BaiQi dark wrist band '+side,cloth),'Ring3' if side=='l' else 'Ring','hand_'+side)
    band('BaiQi white sleeve cuff '+side,e+axis*length*.61,4.0,3.7,material('BaiQi white cuff '+side,white),'Sleeve2' if side=='l' else 'Sleeve','lowerarm_'+side)
    band('BaiQi gold cuff edge '+side,e+axis*length*.67,.65,3.76,goldmat,'Sleeve2' if side=='l' else 'Sleeve','lowerarm_'+side)
# Blue armband bow: source flat art becomes a thick curved accessory, aligned
# from source arm coordinates to the native upper arm before skin binding.
sa=np.array(pixel_cm(558,686));se=np.array(pixel_cm(474,880));ta=arm.data.bones['upperarm_r'].head_local;te=arm.data.bones['lowerarm_r'].head_local
sd=(se-sa)/np.linalg.norm(se-sa);td=np.array([te.x-ta.x,te.z-ta.z]);td/=np.linalg.norm(td)
def arm_map(co):
    q=np.array([co[0],co[2]])-sa;dest=np.array([ta.x,ta.z])+td*np.dot(q,sd)*(te-ta).length/np.linalg.norm(se-sa)+np.array([-td[1],td[0]])*np.dot(q,[-sd[1],sd[0]])
    return (float(dest[0]),float(ta.y-6),float(dest[1]))
source_grid('BaiQi navy arm ribbon','bandage','Bandage',{'Bandage'},lambda x,z:0,arm_map,'upperarm_r',2)
# Optional original machine and ponytails remain editable separate accessories.
for name,part,bone,depth in [('machine','Machine','spine_05',-2),('ponytails','Ponytail','head',8),('hand_ring','Part34','hand_r',-8)]:
    obj=source_grid('BaiQi optional '+name,name+'_enabled',part,desc(part),lambda x,z:depth,bone=bone,step=2)
    if obj:obj.hide_render=True;obj.hide_set(True);obj['default_visible']=False;obj['optional_state_pending_review']=True
obj=source_grid('BaiQi optional constellation effect','Part40_diagnostic','Part40',{'Part40'},lambda x,z:-12,bone='pelvis',step=3)
if obj:obj.hide_render=True;obj.hide_set(True);obj['default_visible']=False;obj['source_state']='diagnostic reveal; original parameter trigger pending'
report={'character':'白绮','status':'full_assembly_prototype_not_accepted','female_foundation':'anatomy_foundation_003','native_bones':len(arm.data.bones),'objects':records,'open_defects':['All garments require multi-view collision and contour review','Hair side seam and rear volume need refinement','Expression states not yet connected','Alternate hand pose and optional accessory controls pending','Full shape and ROM renders not completed','Game material conversion not completed']}
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'BaiQi_Assembly.blend'));(OUT/'assembly_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('BAIQI_FULL_ASSEMBLY_PROTOTYPE',len(records),flush=True)
