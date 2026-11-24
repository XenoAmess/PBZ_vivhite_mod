"""Render a replacement input in the exact existing ROM scene/actions."""
import argparse,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--scene',default='output/live2d_delta/qa_runs/repair_005/Delta_SelfTest.blend');p.add_argument('--output',required=True);p.add_argument('--clay',action='store_true')
p.add_argument('--path-traced',action='store_true');p.add_argument('--neutral-only',action='store_true')
p.add_argument('--flat',action='store_true')
p.add_argument('--body',action='store_true')
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=(ROOT/args.output).resolve();assert out.is_relative_to(ROOT);out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/args.scene));arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');old=next(o for o in bpy.data.objects if o.type=='MESH')
before=set(bpy.data.objects)
with bpy.data.libraries.load(str(ROOT/args.candidate),link=False) as (source,target):target.objects=source.objects
for o in target.objects:
    if o and o.name not in bpy.context.scene.objects:bpy.context.scene.collection.objects.link(o)
loaded=[o for o in bpy.data.objects if o not in before]
new=next(o for o in loaded if o.type=='MESH');own_arm=next(o for o in loaded if o.type=='ARMATURE')
new.parent=arm
for m in new.modifiers:
    if m.type=='ARMATURE':m.object=arm
bpy.data.objects.remove(old,do_unlink=True);bpy.data.objects.remove(own_arm,do_unlink=True)
scene=bpy.context.scene;scene.render.resolution_x=768;scene.render.resolution_y=768
if args.clay:
    gray=bpy.data.materials.new('Preflight clay');gray.diffuse_color=(.36,.4,.44,1);gray.use_nodes=True
    gray.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.36,.4,.44,1)
    for i in range(len(new.data.materials)):new.data.materials[i]=gray
if args.path_traced:scene.render.engine='CYCLES';scene.cycles.samples=16
if args.flat:
    new.data.normals_split_custom_set([(0,0,0)]*len(new.data.loops))
    for polygon in new.data.polygons:polygon.use_smooth=False
arm.animation_data.action=bpy.data.actions['DeltaTest_neck_pitch']
for pose,frame in [('neutral',45),('up35',77)]:
    if args.neutral_only and pose!='neutral':continue
    scene.frame_set(frame);bpy.context.view_layer.update()
    for name,location in [('front',(0,-500,170)),('side',(500,0,170)),('oblique',(330,-420,172))]:
        cam=scene.camera;cam.data.ortho_scale=68;cam.location=location
        cam.rotation_euler=(Vector((0,0,168))-cam.location).to_track_quat('-Z','Y').to_euler()
        if args.body:
            cam.data.ortho_scale=230;cam.location=(location[0],location[1],105)
            cam.rotation_euler=(Vector((0,0,101))-cam.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(out/(pose+'_'+name+'.png'));bpy.ops.render.render(write_still=True)
(out/'README.txt').write_text('Material/shape preflight in the existing ROM scene. This is not a complete acceptance run.\n',encoding='utf-8')
print('QA_PREFLIGHT_READY',out)
