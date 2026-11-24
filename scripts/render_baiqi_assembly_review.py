"""Review the actual multi-object BaiQi assembly with alpha-preserving clay."""
import argparse,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--candidate',default='output/live2d_delta/baiqi_head_prototype_001/BaiQi_Head_Assembly.blend');p.add_argument('--output',default='output/live2d_delta/baiqi_head_prototype_001/review');p.add_argument('--full-body',action='store_true');args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=ROOT/args.output;out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/args.candidate));arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');meshes=[o for o in bpy.data.objects if o.type=='MESH']
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX';scene.world=bpy.data.worlds.new('BaiQi assembly studio');scene.world.color=(.1,.1,.1)
for loc,energy,size in [((180,-330,340),2400000,250),((-260,-150,240),1300000,250),((0,260,340),1900000,250)]:
    data=bpy.data.lights.new('Assembly softbox','AREA');data.energy=energy;data.size=size;obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.location=loc;obj.rotation_euler=(Vector((0,0,168))-obj.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('Assembly camera');cam=bpy.data.objects.new(data.name,data);scene.collection.objects.link(cam);scene.camera=cam;data.type='ORTHO';data.ortho_scale=225 if args.full_body else 68;data.clip_end=10000
with bpy.data.libraries.load(str(ROOT/'output/live2d_delta/qa_runs/repair_005/Delta_SelfTest.blend'),link=False) as (source,target):target.actions=['DeltaTest_neck_pitch']
arm.animation_data_create();arm.animation_data.action=target.actions[0]
original={o.name:list(o.data.materials) for o in meshes};clay={}
for mats in original.values():
    for mat in mats:
        if mat.name in clay:continue
        copy=mat.copy();copy.name='Alpha_preserved_clay_'+mat.name
        bsdf=copy.node_tree.nodes.get('Principled BSDF')
        if bsdf:
            for link in list(bsdf.inputs['Base Color'].links):copy.node_tree.links.remove(link)
            bsdf.inputs['Base Color'].default_value=(.36,.4,.44,1);bsdf.inputs['Roughness'].default_value=.85
        clay[mat.name]=copy
images=[]
for kind in ['textured','clay']:
    for obj in meshes:
        for i,mat in enumerate(original[obj.name]):obj.data.materials[i]=clay[mat.name] if kind=='clay' else mat
    for pose,frame in [('neutral',45),('up35',77)]:
        scene.frame_set(frame);bpy.context.view_layer.update()
        for view,location in [('front',(0,-500,178)),('side',(500,0,178)),('oblique',(330,-420,178)),('back',(0,500,178))]:
            cam.location=(location[0],location[1],103) if args.full_body else location;cam.rotation_euler=(Vector((0,3,103 if args.full_body else 176))-cam.location).to_track_quat('-Z','Y').to_euler();folder=out/kind;folder.mkdir(exist_ok=True);path=folder/(pose+'_'+view+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True);images.append(path.relative_to(out).as_posix())
for obj in meshes:
    for i,mat in enumerate(original[obj.name]):obj.data.materials[i]=mat
scene.frame_set(45);bpy.ops.wm.save_as_mainfile(filepath=str(out/'BaiQi_Head_Review.blend'))
(out/'review_manifest.json').write_text(json.dumps({'candidate':args.candidate,'images':images,'status':'prototype_pending_review','clay_preserves_actual_alpha_masks':True},indent=2));print('BAIQI_ASSEMBLY_REVIEW_READY',len(images))
