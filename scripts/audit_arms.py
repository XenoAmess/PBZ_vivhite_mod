"""Compare original/before/after meshes driven by the same real game action.

Using one shared native armature isolates model/weight differences. These are
raw animation clips, without the live game AnimBP's IK and postprocess layers.
"""
import json
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/live2d_delta/arm_audit';OUT.mkdir(parents=True,exist_ok=True)
if '--output' in sys.argv:OUT=Path(sys.argv[sys.argv.index('--output')+1]).resolve();OUT.mkdir(parents=True,exist_ok=True)
AFTER=sys.argv[sys.argv.index('--after')+1] if '--after' in sys.argv else 'arm_audit_after'
BEFORE=sys.argv[sys.argv.index('--before')+1] if '--before' in sys.argv else 'arm_audit_before'
sys.path[:0]=[str(ROOT/'tools/blender_libs'),str(ROOT/'vendor/UEFormat/plugins/blender')]
from io_scene_ueformat.importer.import_context import UEFormatImport
from io_scene_ueformat.options import UEAnimOptions,UEModelOptions

bpy.ops.wm.read_factory_settings(use_empty=True)
native=ROOT/'artifacts/extracted/original/HuaShira/Characters/Hero/Hero_Hun/SkinParts/Hun_Body_Simple.uemodel'
UEFormatImport(UEModelOptions(scale_factor=1.,reorient_bones=False,import_sockets=False,import_morph_targets=False)).import_file(native)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');original=next(o for o in bpy.data.objects if o.type=='MESH')
reference={b.name:arm.matrix_world@b.matrix_local for b in arm.data.bones}
gray=bpy.data.materials.new('Original gray');gray.diffuse_color=(.28,.30,.34,1);gray.use_nodes=True
gray.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=gray.diffuse_color
gray.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.9
original.data.materials.clear();original.data.materials.append(gray)
for p in original.data.polygons:p.material_index=0
models=[original];rest_comparison={}
for key,folder in [('before',BEFORE),('after',AFTER)]:
    blend=ROOT/'build'/folder/'Delta_adult.blend'
    before=set(bpy.data.objects)
    with bpy.data.libraries.load(str(blend),link=False) as (source,target):
        target.objects=source.objects
    for obj in target.objects:
        if obj and obj.name not in bpy.context.scene.objects:bpy.context.scene.collection.objects.link(obj)
    imported=[o for o in bpy.data.objects if o not in before]
    own_arm=next(o for o in imported if o.type=='ARMATURE')
    mesh=next(o for o in imported if o.type=='MESH')
    differences=[]
    for b in own_arm.data.bones:
        matrix=own_arm.matrix_world@b.matrix_local
        ref=reference[b.name]
        differences.append({'bone':b.name,'head_error_cm':float((matrix.translation-ref.translation).length),
                            'rotation_error_rad':float(matrix.to_quaternion().rotation_difference(ref.to_quaternion()).angle)})
    rest_comparison[key]={'maximum_head_error_cm':max(d['head_error_cm'] for d in differences),
                          'maximum_rotation_error_rad':max(d['rotation_error_rad'] for d in differences)}
    mesh.parent=arm
    for modifier in mesh.modifiers:
        if modifier.type=='ARMATURE':modifier.object=arm
    for obj in imported:
        if obj is not mesh:bpy.data.objects.remove(obj,do_unlink=True)
    mesh.name='Delta_'+key
    # Restore the unlit original artwork for a legible comparison.
    for mat in mesh.data.materials:
        if mat and 'Delta_Live2D_Front' in mat.name:
            emission=next((n for n in mat.node_tree.nodes if n.type=='EMISSION'),None)
            if emission:mat.node_tree.links.new(emission.outputs[0],mat.node_tree.nodes['Material Output'].inputs['Surface'])
    models.append(mesh)

scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=2100;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard'
scene.world=bpy.data.worlds.new('Audit studio');scene.world.color=(.09,.09,.09)
for location,energy,size in [((300,-400,500),3600000,400),((-300,-100,300),1800000,300),((0,300,400),2400000,300)]:
    data=bpy.data.lights.new('Audit light','AREA');data.energy=energy;data.size=size
    obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.location=location
    obj.rotation_euler=(Vector((0,0,120))-obj.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('Audit camera');camera=bpy.data.objects.new(data.name,data);scene.collection.objects.link(camera)
scene.camera=camera;data.type='ORTHO';data.ortho_scale=640
data.clip_start=.1;data.clip_end=10000.
camera.location=(0,-1000,120);camera.rotation_euler=(Vector((0,0,120))-camera.location).to_track_quat('-Z','Y').to_euler()
offsets=[-180.,0.,180.]
labels=[]
for text,x in zip(['Original Soul','Delta: previous','Delta: current'],offsets):
    font=bpy.data.curves.new(text,'FONT');font.body=text;font.align_x='CENTER';font.size=7
    obj=bpy.data.objects.new(text,font);scene.collection.objects.link(obj);obj.location=(x,-220,235)
    obj.rotation_euler=(np.pi/2,0,0)
    labels.append(obj)

for mesh in models:mesh.hide_render=True
animations={name:next((ROOT/'artifacts/extracted/arm_audit').rglob(name+'.ueanim')) for name in
    ['Hun_Unarmed_Idle_Loop','Hun_Unarmed_Run_Fwd_Loop','Hun_BaiShanDual_Attack_A']}
if '--extended' in sys.argv:
    animations.update({p.stem:p for p in (ROOT/'artifacts/extracted/arm_extended').rglob('*.ueanim')})
if '--only' in sys.argv:
    wanted=sys.argv[sys.argv.index('--only')+1].split(',')
    animations={n:p for n,p in animations.items() if n in wanted}
worst_frames={}
if '--worst-frames' in sys.argv:
    worst_frames=json.loads(Path(sys.argv[sys.argv.index('--worst-frames')+1]).read_text())['clips']
report={'control':'All three meshes use the identical native game armature and action at each frame',
        'rest_comparison':rest_comparison,'clips':{},
        'limits':['No live AnimBP IK or postprocess simulation','Offline geometry audit, not an in-game test']}
edge_inputs={}
for mesh in models:
    vertices=np.array([(mesh.matrix_world@v.co)[:] for v in mesh.data.vertices])
    edges=np.array([e.vertices[:] for e in mesh.data.edges])
    rest_lengths=np.linalg.norm(vertices[edges[:,0]]-vertices[edges[:,1]],axis=1)
    names={g.index:g.name for g in mesh.vertex_groups}
    masks={}
    for region,parts in [('arms',['upperarm','lowerarm','hand','thumb','index','middle','ring','pinky','wrist']),
                         ('hands',['hand','thumb','index','middle','ring','pinky','wrist'])]:
        included=np.array([sum(g.weight for g in v.groups if any(k in names[g.group] for k in parts))>.7 for v in mesh.data.vertices])
        masks[region]=included[edges[:,0]]&included[edges[:,1]]&(rest_lengths>.01)
    edge_inputs[mesh.name]=(edges,rest_lengths,masks)
joint_materials=[]
for name,color in [('Shoulder',(0.05,1.,.15,1)),('Elbow',(1.,.32,.01,1)),('Wrist',(.03,.75,1.,1))]:
    mat=bpy.data.materials.new(name);mat.use_nodes=True
    node=mat.node_tree.nodes.new('ShaderNodeEmission');node.inputs[0].default_value=color
    mat.node_tree.links.new(node.outputs[0],mat.node_tree.nodes['Material Output'].inputs[0]);joint_materials.append(mat)
for name,path in animations.items():
    action,dto=UEFormatImport(UEAnimOptions(scale_factor=1.,override_skeleton=arm,import_curves=False)).import_file_with_dto(path)
    assert dto.metadata and int(dto.metadata.additive_anim_type)==0,'Use non-additive control clips'
    frames=sorted(set([0,int((dto.metadata.num_frames-1)*.25),int((dto.metadata.num_frames-1)*.5),int((dto.metadata.num_frames-1)*.75)]))
    if name in worst_frames:
        row=worst_frames[name]
        frames=sorted(set(frames+[row['worst']['arms']['frame'],row['worst']['upperarms']['frame'],row['hotspots'][0]['frame']]))
    if '--frames' in sys.argv:frames=[int(f) for f in sys.argv[sys.argv.index('--frames')+1].split(',') if int(f)<dto.metadata.num_frames]
    clip={'frames':frames,'total_frames':dto.metadata.num_frames,'fps':dto.metadata.frames_per_second,'samples':[]}
    for frame in frames:
        scene.frame_set(frame);bpy.context.view_layer.update();depsgraph=bpy.context.evaluated_depsgraph_get()
        root_motion=arm.matrix_world@arm.pose.bones['root'].head-reference['root'].translation
        temporary=[];metrics=[];markers=[]
        for source,x in zip(models,offsets):
            evaluated=source.evaluated_get(depsgraph)
            geometry=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=depsgraph)
            sample=bpy.data.objects.new('Audit evaluated',geometry);scene.collection.objects.link(sample)
            sample.matrix_world=source.matrix_world.copy();sample.location.x+=x
            sample.location-=root_motion
            temporary.append(sample)
            vertices=np.array([(source.matrix_world@v.co)[:] for v in geometry.vertices])
            assert np.isfinite(vertices).all()
            edges,rest_lengths,masks=edge_inputs[source.name]
            lengths=np.linalg.norm(vertices[edges[:,0]]-vertices[edges[:,1]],axis=1)
            regions={}
            for region,mask in masks.items():
                ratios=lengths[mask]/rest_lengths[mask]
                regions[region]={'edges':int(mask.sum()),'stretch_p95':float(np.percentile(ratios,95)),
                                 'stretch_p99':float(np.percentile(ratios,99)),
                                 'stretch_max':float(ratios.max()),'edges_over_2x':int((ratios>2).sum())}
            metrics.append({'model':source.name,'bounds_cm':[vertices.min(axis=0).tolist(),vertices.max(axis=0).tolist()],
                            'posed_edge_ratio':regions})
            for side in ['l','r']:
                for index,bone_name in enumerate(['upperarm_'+side,'lowerarm_'+side,'hand_'+side]):
                    position=arm.matrix_world@arm.pose.bones[bone_name].head-root_motion
                    # Orthographic front overlay: same projected X/Z, in front of the surfaces.
                    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=1.6,
                        location=(position.x+x,-200,position.z))
                    marker=bpy.context.object;marker.data.materials.append(joint_materials[index]);temporary.append(marker)
                    markers.append((marker,position+Vector((x,0,0))))
        views=[('',Vector((0,-1000,120)))]
        if '--three-quarter' in sys.argv:views.append(('_3q',Vector((500,-866,120))))
        for suffix,location in views:
            camera.location=location
            camera.rotation_euler=(Vector((0,0,120))-location).to_track_quat('-Z','Y').to_euler()
            facing=(location-Vector((0,0,120))).normalized()
            for marker,position in markers:marker.location=position+facing*200
            for label in labels:label.rotation_euler=camera.rotation_euler
            scene.render.filepath=str(OUT/f'{name}_f{frame:03}{suffix}.png');bpy.ops.render.render(write_still=True)
        clip['samples'].append({'frame':frame,'models':metrics})
        for obj in temporary:
            data=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
            if data.users==0:bpy.data.meshes.remove(data)
    report['clips'][name]=clip
(OUT/'audit_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ARM_AUDIT_RENDERED',len(report['clips']),'actual game animation clips')
