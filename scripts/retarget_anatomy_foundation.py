"""Fit a CC0 authored anatomical foundation to the unchanged adult rig.

This is a gray modeling foundation, not the Delta character or a Mod release.
Visible character design and garments still require reconstruction and QA.
"""
import argparse,json,struct,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--skin-only',action='store_true');args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=(ROOT/args.output).resolve();assert out.is_relative_to(ROOT);out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'build/qa_pre_inputs_015/Delta_adult.blend'))
native=next(o for o in bpy.data.objects if o.type=='ARMATURE');rest_before={b.name:(b.matrix_local.copy(),b.parent.name if b.parent else None) for b in native.data.bones}
for obj in list(bpy.data.objects):
    if obj.type=='MESH':bpy.data.objects.remove(obj,do_unlink=True)
before=set(bpy.data.objects)
with bpy.data.libraries.load(str(ROOT/'artifacts/anatomy_base/Base_Female.blend'),link=False) as (source,target):target.objects=source.objects
loaded=[o for o in target.objects if o]
for o in loaded:
    if o.name not in bpy.context.scene.objects:bpy.context.scene.collection.objects.link(o)
rig=next(o for o in loaded if o.type=='ARMATURE');meshes=[o for o in loaded if o.type=='MESH' and o.name in ['Body','Face']]
raw=(ROOT/'artifacts/anatomy_base/Base_Female.glb').read_bytes();meta=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]])
human={b['bone']:meta['nodes'][b['node']]['name'] for b in meta['extensions']['VRM']['humanoid']['humanBones']}
assert meta['extensions']['VRM']['meta']['licenseName']=='CC0'
mapping={'hips':'pelvis','spine':'spine_01','chest':'spine_03','upperChest':'spine_05','neck':'neck_01','head':'head'}
for side in ['left','right']:
    suffix='l' if side=='left' else 'r'
    for a,b in [('Shoulder','clavicle'),('UpperArm','upperarm'),('LowerArm','lowerarm'),('Hand','hand'),('UpperLeg','thigh'),('LowerLeg','calf'),('Foot','foot'),('Toes','ball')]:mapping[side+a]=b+'_'+suffix
    for digit in ['Thumb','Index','Middle','Ring','Little']:
        for index,joint in enumerate(['Proximal','Intermediate','Distal'],1):mapping[side+digit+joint]=('pinky' if digit=='Little' else digit.lower())+f'_{index:02}_'+suffix
mapping={human[h]:n for h,n in mapping.items() if h in human and n in native.data.bones}
turn=Matrix.Diagonal(Vector((-1,-1,1)))
source_points={name:turn@(rig.matrix_world@b.head_local)*100 for name,b in rig.data.bones.items()}
target_points={name:(native.matrix_world@native.data.bones[n].head_local).copy() for name,n in mapping.items()}
anchors={'spine_01':(0,5.1,115),'spine_03':(0,4.8,130),'spine_05':(0,4.0,143),'neck_01':(0,4.8,159),'head':(0,5.4,169)}
for name,n in mapping.items():
    if n in anchors:target_points[name]=Vector(anchors[n])
def mapped_ancestor(name):
    bone=rig.data.bones.get(name)
    while bone:
        if bone.name in mapping:return bone.name
        bone=bone.parent
    return human['hips']
def frame(direction,back=Vector((0,1,0))):
    axis=direction.normalized();normal=back-axis*back.dot(axis)
    if normal.length<.01:normal=Vector((1,0,0))-axis*axis.x
    normal.normalize();side=normal.cross(axis).normalized()
    return np.column_stack([axis[:],side[:],normal[:]])
transforms={}
for name,target_name in mapping.items():
    children=[b.name for b in rig.data.bones[name].children if b.name in mapping]
    if children:
        child=next((n for n in children if 'UpperArm' not in n),children[0]);sd=source_points[child]-source_points[name];td=target_points[child]-target_points[name]
    else:
        parent=mapped_ancestor(rig.data.bones[name].parent.name);sd=source_points[name]-source_points[parent];td=target_points[name]-target_points[parent]
    if target_name=='head':linear=np.eye(3)*1.1
    else:
        if sd.length<.001:sd=Vector((0,0,1))
        if td.length<.001:td=sd.copy()
        radial=1.10 if target_name.startswith('neck') else 1.18
        linear=frame(td)@np.diag([td.length/sd.length,radial,radial])@frame(sd).T
    transforms[name]=(linear,np.array(source_points[name]),np.array(target_points[name]))
clay=bpy.data.materials.new('Anatomical foundation clay');clay.use_nodes=True;clay.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.36,.40,.44,1)
source_surfaces=[]
for obj in meshes:
    classes=[m.name for m in obj.data.materials]
    source_surfaces.append({'object':obj.name,'materials':classes,'polygon_counts':{name:sum(poly.material_index==i for poly in obj.data.polygons) for i,name in enumerate(classes)}})
    tag=obj.data.attributes.new('anatomy_source_material','INT','FACE')
    for poly,item in zip(obj.data.polygons,tag.data):item.value=poly.material_index
    obj['anatomy_source_materials']=json.dumps(classes)
    if args.skin_only:
        import bmesh
        bm=bmesh.new();bm.from_mesh(obj.data)
        allowed=[i for i,name in enumerate(classes) if ('_SKIN' in name or '_HairBack_' in name) or (obj.name=='Face' and any(part in name for part in ['FaceMouth','EyeWhite','EyeIris']))]
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.material_index not in allowed],context='FACES')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS');bm.to_mesh(obj.data);bm.free()
    positions=[turn@(obj.matrix_world@v.co)*100 for v in obj.data.vertices]
    weights=[];new_positions=[]
    for v,position in zip(obj.data.vertices,positions):
        influences={}
        for item in v.groups:
            name=mapped_ancestor(obj.vertex_groups[item.group].name);influences[name]=influences.get(name,0)+item.weight
        total=sum(influences.values());assert total>.001
        influences={name:w/total for name,w in influences.items()}
        fitted=np.zeros(3);native_weights={}
        for name,weight in influences.items():
            linear,a,b=transforms[name];fitted+=weight*(b+linear@(np.array(position)-a));n=mapping[name];native_weights[n]=native_weights.get(n,0)+weight
        new_positions.append(fitted);weights.append(native_weights)
    if obj.data.shape_keys:obj.shape_key_clear()
    obj.vertex_groups.clear();groups={n:obj.vertex_groups.new(name=n) for n in sorted(set(mapping.values()))}
    obj.parent=None;obj.matrix_world=Matrix.Identity(4)
    for v,position,influences in zip(obj.data.vertices,new_positions,weights):
        v.co=position
        for name,weight in influences.items():groups[name].add([v.index],weight,'REPLACE')
    obj.modifiers.clear();obj.parent=native;mod=obj.modifiers.new('Unchanged adult native skeleton','ARMATURE');mod.object=native;mod.use_deform_preserve_volume=False
    obj.data.materials.clear();obj.data.materials.append(clay)
    for poly in obj.data.polygons:poly.material_index=0;poly.use_smooth=True
    obj.data.normals_split_custom_set([(0,0,0)]*len(obj.data.loops))
for obj in loaded:
    if obj not in meshes:bpy.data.objects.remove(obj,do_unlink=True)
bpy.ops.object.select_all(action='DESELECT')
for obj in meshes:obj.select_set(True)
bpy.context.view_layer.objects.active=meshes[0];bpy.ops.object.join();mesh=bpy.context.object;mesh.name='AnatomicalFoundation_WIP'
assert len(native.data.bones)==264
for bone in native.data.bones:
    old,parent=rest_before[bone.name];assert bone.matrix_local==old and (bone.parent.name if bone.parent else None)==parent
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Delta_adult.blend'))
report={'source':'VRoid Project Base_Female (CC0), anatomy foundation only','license_source':'https://vroid.pixiv.help/hc/en-us/articles/4402614652569','native_rig_unchanged':True,'mapped_source_bones':len(mapping),'vertices':len(mesh.data.vertices),'status':'foundation_only_pending_whole_body_review','target_geometry_anchors_cm':anchors,'source_surfaces':source_surfaces,'skin_only':args.skin_only}
(out/'foundation_report.json').write_text(json.dumps(report,indent=2));print('ANATOMY_FOUNDATION_READY',json.dumps(report))
