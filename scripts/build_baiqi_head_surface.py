"""BaiQi appearance on an authored female head, with curved solid accessories.

Face artwork is a material on the anatomical surface. Hair, glasses and bows
are separate surfaces; no coincident facial decal stack is retained.
"""
import argparse,json,math,sys
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--base',default='output/live2d_delta/anatomy_foundation_003/Delta_adult.blend');p.add_argument('--output',default='output/live2d_delta/baiqi_head_surface_006');args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);OUT=ROOT/args.output;OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/args.base))
base=next(o for o in bpy.data.objects if o.type=='MESH');arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');base.name='BaiQi_FemaleFoundation'
if arm.animation_data:arm.animation_data_clear()
for b in arm.pose.bones:b.matrix_basis.identity()
LAYER=ROOT/'artifacts/baiqi_component_audit/head_layers';SCALE=195/1607
def px_to_cm(px,py):return ((px-694.5)*SCALE,165.35+(600-py)*SCALE)
def cm_to_uv(x,z):return ((x/SCALE+694.5)/1400,1-(600-(z-165.35)/SCALE)/2200)
skin=(.965,.823,.758,1)
def simple(name,color):
    m=bpy.data.materials.new(name);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=color;b.inputs['Roughness'].default_value=.82;return m
skinmat=simple('BaiQi Skin',skin)
def image_mat(name,path,face=False):
    m=simple(name,skin if face else (1,1,1,1));m.surface_render_method='DITHERED';m.use_backface_culling=False
    n=m.node_tree.nodes;l=m.node_tree.links;b=n['Principled BSDF'];im=bpy.data.images.load(str(path),check_existing=True);im.pack();t=n.new('ShaderNodeTexImage');t.image=im
    uv=n.new('ShaderNodeUVMap');uv.uv_map='BaiQiCanvas';l.new(uv.outputs['UV'],t.inputs['Vector'])
    if face:
        mix=n.new('ShaderNodeMixRGB');mix.blend_type='MIX';mix.inputs[1].default_value=skin;l.new(t.outputs['Alpha'],mix.inputs[0]);l.new(t.outputs['Color'],mix.inputs[2]);l.new(mix.outputs['Color'],b.inputs['Base Color'])
    else:l.new(t.outputs['Color'],b.inputs['Base Color']);l.new(t.outputs['Alpha'],b.inputs['Alpha'])
    return m
face_mat=image_mat('BaiQi original face appearance',LAYER/'face.png',True)
# Retain one eyeball surface per eye. The old iris is removed rather than
# projecting the same new artwork onto two almost coincident surfaces.
bm=bmesh.new();bm.from_mesh(base.data);tag=bm.faces.layers.int['anatomy_source_material']
bmesh.ops.delete(bm,geom=[f for f in bm.faces if f[tag]==5 and all(v.co.z>172 and v.co.y<0 for v in f.verts)],context='FACES')
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0001)
bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS');bm.to_mesh(base.data);bm.free()
base.data.materials.clear();base.data.materials.append(skinmat);base.data.materials.append(face_mat)
tag=base.data.attributes['anatomy_source_material'];uv=base.data.uv_layers.new(name='BaiQiCanvas')
for poly in base.data.polygons:
    front=all(base.data.vertices[i].co.z>164 for i in poly.vertices) and poly.center.y<2
    poly.material_index=1 if front else 0
    for li in poly.loop_indices:
        co=base.data.vertices[base.data.loops[li].vertex_index].co;uv.data[li].uv=cm_to_uv(co.x,co.z)
coords=[base.matrix_world@v.co for v in base.data.vertices];head_faces=[list(p.vertices) for p in base.data.polygons if min(coords[i].z for i in p.vertices)>164]
tree=BVHTree.FromPolygons(coords,head_faces)
source=json.loads((ROOT/'repro/baiqi_source/core_geometry.json').read_text(encoding='utf-8'));parts={p['id']:p for p in source['parts']}
root=bpy.data.collections.new('BaiQi source component mapping');bpy.context.scene.collection.children.link(root);cols={p['id']:bpy.data.collections.new('BaiQi '+p['id']+' '+p['source_name']) for p in source['parts']}
for p in source['parts']:(cols[p['parent']] if p['parent'] else root).children.link(cols[p['id']])
def descendants(part):
    ids={part}
    for c in parts[part]['children']:ids.update(descendants(c))
    return ids
layers=json.loads((LAYER/'manifest.json').read_text());records=[]
def bind(obj,part,contributors):
    cols[part].objects.link(obj);obj.parent=arm;obj.vertex_groups.new(name='head').add(list(range(len(obj.data.vertices))),1,'REPLACE');m=obj.modifiers.new('Native adult linear skin','ARMATURE');m.object=arm
    obj['baiqi_source_parts']=json.dumps(sorted(contributors));obj['migration_status']='assembled_pending_review';records.append({'object':obj.name,'source_parts':sorted(contributors)})
    for p in obj.data.polygons:p.use_smooth=True
def read_image(path):
    im=bpy.data.images.load(str(path),check_existing=True);a=np.empty(len(im.pixels),dtype=np.float32);im.pixels.foreach_get(a);return a.reshape(im.size[1],im.size[0],4)[::-1]
back=read_image(LAYER/'hair_back.png');profile=[]
for py in range(300,700):
    xs=np.flatnonzero(back[py,:,3]>.5)
    if len(xs)>2:
        x0,z=px_to_cm(xs[0],py);x1,_=px_to_cm(xs[-1],py);profile.append((z,max(abs(x0),abs(x1))))
profile.sort();zs=[i[0] for i in profile];radii=[i[1] for i in profile]
shape=np.array([(165.2,10.7,8.2),(169,13.0,10.0),(177,15.0,12.0),(185,14.8,12.0),(190,12.5,10.0),(194,8.3,6.7),(196.8,.15,.15)])
def smooth_profile(z,k):
    i=max(0,min(len(shape)-2,int(np.searchsorted(shape[:,0],z)-1)));a,b=shape[i:i+2];t=float(np.clip((z-a[0])/(b[0]-a[0]),0,1));h=b[0]-a[0]
    slope=lambda j:(shape[min(len(shape)-1,j+1),k]-shape[max(0,j-1),k])/(shape[min(len(shape)-1,j+1),0]-shape[max(0,j-1),0])
    return (2*t**3-3*t*t+1)*a[k]+(t**3-2*t*t+t)*h*slope(i)+(-2*t**3+3*t*t)*b[k]+(t**3-t*t)*h*slope(i+1)
def hair_depth(x,z,backside=False):
    rx=max(.5,smooth_profile(z,1));ry=max(.5,smooth_profile(z,2))+3.3;cy=6.7
    depth=ry*math.sqrt(max(.005,1-(x/rx)**2));y=cy+(depth if backside else -depth)
    return y
def surface(name,filename,part,contributors,depth,step=3,solid=.16):
    rgba=read_image(LAYER/filename);mask=rgba[:,:,3]>.15;rows,columns=np.nonzero(mask);y0=max(0,int(rows.min())-step);y1=min(2200,int(rows.max())+step*2);x0=max(0,int(columns.min())-step);x1=min(1400,int(columns.max())+step*2)
    vertices=[];faces=[];lookup={};texcoords=[]
    def vert(px,py):
        key=(px,py)
        if key not in lookup:
            x,z=px_to_cm(px,py);lookup[key]=len(vertices);vertices.append((x,depth(x,z),z));texcoords.append((px/1400,1-py/2200))
        return lookup[key]
    for py in range(y0,y1-step,step):
        for px in range(x0,x1-step,step):
            if mask[py:py+step+1,px:px+step+1].any():faces.append([vert(px,py),vert(px,py+step),vert(px+step,py+step),vert(px+step,py)])
    data=bpy.data.meshes.new(name);data.from_pydata(vertices,[],faces);data.materials.append(image_mat(name+' appearance',LAYER/filename));uv=data.uv_layers.new(name='BaiQiCanvas')
    for p in data.polygons:
        for li in p.loop_indices:uv.data[li].uv=texcoords[data.loops[li].vertex_index]
    obj=bpy.data.objects.new(name,data);bind(obj,part,contributors)
    if solid:m=obj.modifiers.new('Physical thickness cm','SOLIDIFY');m.thickness=solid;m.offset=0
    return obj
surface('BaiQi bob front','hair_front.png','Fhair',next(l['source_parts'] for l in layers if l['layer']=='hair_front'),lambda x,z:hair_depth(x,z),3,.12)
# Rounded side/back continuation uses the source outline; the unseen depth is
# authored and must be judged in side/back review, not called source evidence.
v=[];f=[];uvs=[]
for z in np.linspace(165.2,196.0,100):
    rx=smooth_profile(z,1);ry=smooth_profile(z,2)
    py=int(np.clip(600-(z-165.35)/SCALE,0,2199));xs=np.flatnonzero(back[py,:,3]>.5)
    if len(xs)<2:
        py=int(np.clip(py,355,610));xs=np.flatnonzero(back[py,:,3]>.5)
    lo,hi=(float(xs[0])+2,float(xs[-1])-2) if len(xs)>3 else (690,700)
    for j in range(49):
        theta=math.pi*j/48;x=rx*math.cos(theta);t=(z-165.2)/(196.0-165.2);actual_z=z+(1-t)**4*(2.5*math.sin(theta)-.65*math.cos(theta*12));v.append((x,6.7+ry*math.sin(theta),actual_z));uvs.append((((lo+hi)/2+(hi-lo)*.48*math.cos(theta))/1400,1-py/2200))
for i in range(len(v)//49-1):
    for j in range(48):a=i*49+j;f.append((a,a+1,a+50,a+49))
data=bpy.data.meshes.new('BaiQi rounded rear hair');data.from_pydata(v,[],f);mat=image_mat('BaiQi side hair source color',LAYER/'hair_back_opaque.png');alpha=mat.node_tree.nodes['Principled BSDF'].inputs['Alpha'];mat.node_tree.links.remove(alpha.links[0]);alpha.default_value=1;data.materials.append(mat);uv=data.uv_layers.new(name='BaiQiCanvas')
for p in data.polygons:
    for li in p.loop_indices:uv.data[li].uv=uvs[data.loops[li].vertex_index]
obj=bpy.data.objects.new('BaiQi rounded rear hair',data);bind(obj,'Bhair',{'Bhair'})
front=read_image(LAYER/'hair_front.png')
for side in [-1,1]:
    vertices=[];faces=[];texcoords=[]
    for z in np.linspace(166,195.6,120):
        py=int(np.clip(600-(z-165.35)/SCALE,0,2199));xs=np.flatnonzero(front[py,:,3]>.3);xs=xs[xs<694.5] if side<0 else xs[xs>694.5]
        edge=float(xs.min() if side<0 else xs.max()) if len(xs) else 694.5+side*10/SCALE
        x,_=px_to_cm(edge,py);start=Vector((x,hair_depth(x,z),z));end=Vector((side*smooth_profile(z,1),6.7,z))
        for t in np.linspace(0,1,9):
            co=start.lerp(end,t);co.x+=side*.35*math.sin(t*math.pi);vertices.append(co);texcoords.append((edge/1400,1-py/2200))
    for i in range(119):
        for j in range(8):a=i*9+j;faces.append((a,a+1,a+10,a+9))
    data=bpy.data.meshes.new('BaiQi side hair continuation '+str(side));data.from_pydata(vertices,[],faces);data.materials.append(simple('BaiQi side hair pigment '+str(side),(.72,.80,.85,1)));uv=data.uv_layers.new(name='BaiQiCanvas')
    for loop in data.loops:uv.data[loop.index].uv=texcoords[loop.vertex_index]
    obj=bpy.data.objects.new(data.name,data);bind(obj,'Bhair',{'Bhair','Mhair'});obj['inferred_geometry']='side hair volume continuation between source front and rebuilt rear'
def glasses_depth(x,z):
    hit=tree.ray_cast(Vector((x,-100,z)),Vector((0,1,0)),300)[0]
    return (hit.y if hit else -3)-1.0
surface('BaiQi round gold glasses','glasses.png','Glasses',{'Glasses'},glasses_depth,2,.12)
surface('BaiQi black gold headdress','headdress.png','Headdress',descendants('Headdress'),lambda x,z:4+.16*(abs(x)-15),2,.3)
for side in [-1,1]:
    curve=bpy.data.curves.new('BaiQi glasses temple','CURVE');curve.dimensions='3D';curve.bevel_depth=.07;curve.bevel_resolution=2;spline=curve.splines.new('POLY');spline.points.add(3)
    for p,co in zip(spline.points,[(side*11.6,-2,176),(side*11.9,1,176),(side*11.2,5.8,175.7),(side*10.5,6.6,175.2)]):p.co=(*co,1)
    temp=bpy.data.objects.new('BaiQi glasses temple curve '+str(side),curve);bpy.context.scene.collection.objects.link(temp);bpy.context.view_layer.update();data=bpy.data.meshes.new_from_object(temp.evaluated_get(bpy.context.evaluated_depsgraph_get()));bpy.data.objects.remove(temp,do_unlink=True);obj=bpy.data.objects.new('BaiQi glasses temple '+str(side),data)
    obj.data.materials.append(simple('BaiQi gold',(.75,.49,.17,1)));bind(obj,'Glasses',{'Glasses'})
assert len([m for m in base.modifiers if m.type=='ARMATURE' and m.object==arm])==1,'Head accessory construction must preserve body skinning'
records.append({'object':base.name,'source_parts':sorted(descendants('Face')-{'Glasses'}),'method':'appearance baked onto anatomical head material; expression variants pending'})
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'BaiQi_Assembly.blend'))
(OUT/'assembly_report.json').write_text(json.dumps({'character':'白绮','status':'prototype_pending_visual_review','native_bones':len(arm.data.bones),'objects':records,'not_completed':['Body garments and accessories','Alternate ponytails and expression states','Full shape and ROM acceptance','Game material conversion and cook']},ensure_ascii=False,indent=2),encoding='utf-8');print('BAIQI_SURFACE_HEAD_READY',len(records),flush=True)
