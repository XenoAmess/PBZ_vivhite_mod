"""Large clay closeups: same native rig, old and rebuilt upper body."""
import json
import sys
from pathlib import Path
import bpy, bmesh
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools/blender_libs'),str(ROOT/'vendor/UEFormat/plugins/blender')]
from io_scene_ueformat.importer.import_context import UEFormatImport
from io_scene_ueformat.options import UEAnimOptions
TEXTURED='--textured' in sys.argv
ISOLATE='--isolate' in sys.argv
OUT=ROOT/('output/live2d_delta/shoulder_isolated' if ISOLATE else 'output/live2d_delta/shoulder_textured' if TEXTURED else 'output/live2d_delta/shoulder_review');OUT.mkdir(exist_ok=True)
baseline=ROOT/'build/model_inputs_v02/Delta_adult.blend'
if not baseline.is_file():baseline=ROOT/'build/model_inputs/Delta_adult.blend'
bpy.ops.wm.open_mainfile(filepath=str(baseline))
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
old=next(o for o in bpy.data.objects if o.type=='MESH')
before=set(bpy.data.objects)
with bpy.data.libraries.load(str(ROOT/'build/shoulder_inputs/Delta_adult.blend'),link=False) as (source,target):target.objects=source.objects
for obj in target.objects:
    if obj and obj.name not in bpy.context.scene.objects:bpy.context.scene.collection.objects.link(obj)
loaded=[o for o in bpy.data.objects if o not in before]
own_arm=next(o for o in loaded if o.type=='ARMATURE')
new=next(o for o in loaded if o.type=='MESH')
if ISOLATE:
    bm=bmesh.new();bm.from_mesh(new.data);tag=bm.faces.layers.int['rebuild_origin']
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f[tag]!=1],context='FACES')
    bm.to_mesh(new.data);bm.free();new.data.update()
new.parent=arm
for mod in new.modifiers:
    if mod.type=='ARMATURE':mod.object=arm
bpy.data.objects.remove(own_arm,do_unlink=True)
gray=bpy.data.materials.new('Clay');gray.use_nodes=True
gray.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.32,.36,.40,1)
gray.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.8
if not TEXTURED:
    for obj in [old,new]:
        obj.data.materials.clear();obj.data.materials.append(gray)
        for p in obj.data.polygons:p.material_index=0
old.hide_render=True;new.hide_render=True
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=2200;scene.render.resolution_y=1500;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
scene.world=bpy.data.worlds.new('Clay review');scene.world.color=(.08,.08,.08)
for location,energy,size in [((160,-340,420),3200000,300),((-220,-180,260),1500000,250),((0,260,380),2500000,250)]:
    light=bpy.data.lights.new('Review','AREA');light.energy=energy;light.size=size
    obj=bpy.data.objects.new('Review',light);scene.collection.objects.link(obj);obj.location=location
    obj.rotation_euler=(Vector((0,0,155))-obj.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('Review');cam=bpy.data.objects.new('Review',data);scene.collection.objects.link(cam)
scene.camera=cam;data.type='ORTHO';data.ortho_scale=285;data.clip_end=10000
labels=[]
for text,x in [('v0.2',-75),('Upper body trial',75)]:
    font=bpy.data.curves.new(text,'FONT');font.body=text;font.align_x='CENTER';font.size=7
    obj=bpy.data.objects.new(text,font);scene.collection.objects.link(obj);obj.location=(x,-100,235);labels.append(obj)
clips=[('rest',None,0),('idle',next((ROOT/'artifacts/extracted/arm_audit').rglob('Hun_Unarmed_Idle_Loop.ueanim')),77),
       ('raised',next((ROOT/'artifacts/extracted/arm_audit').rglob('Hun_BaiShanDual_Attack_A.ueanim')),23)]
for name,path,frame in clips:
    if path:
        UEFormatImport(UEAnimOptions(scale_factor=1.,override_skeleton=arm,import_curves=False)).import_file(path)
        scene.frame_set(frame)
    else:
        arm.animation_data_clear()
        for bone in arm.pose.bones:bone.matrix_basis.identity()
    bpy.context.view_layer.update()
    temporary=[]
    depsgraph=bpy.context.evaluated_depsgraph_get()
    for source,x in [(old,-75),(new,75)]:
        geometry=bpy.data.meshes.new_from_object(source.evaluated_get(depsgraph),preserve_all_data_layers=True,depsgraph=depsgraph)
        sample=bpy.data.objects.new('Baked review pose',geometry);scene.collection.objects.link(sample)
        sample.matrix_world=source.matrix_world.copy();sample.location.x+=x;temporary.append(sample)
    for view,location in [('front',Vector((0,-900,160))),('oblique',Vector((400,-800,175)))]:
        cam.location=location;cam.rotation_euler=(Vector((0,0,155))-location).to_track_quat('-Z','Y').to_euler()
        for label in labels:label.rotation_euler=cam.rotation_euler
        scene.render.filepath=str(OUT/(name+'_'+view+'.png'));bpy.ops.render.render(write_still=True)
    for obj in temporary:
        geometry=obj.data;bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(geometry)
print('CLAY_SHOULDER_REVIEW_READY',OUT)
