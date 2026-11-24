"""Render all source switches on the actual 3D assembly, not 2D references."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--candidate',default='output/live2d_delta/baiqi_component_assembly_001/BaiQi_Assembly.blend');p.add_argument('--output',default='output/live2d_delta/baiqi_component_assembly_001/variants');args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=ROOT/args.output;out.mkdir(parents=True,exist_ok=True)
candidate=ROOT/args.candidate;bpy.ops.wm.open_mainfile(filepath=str(candidate));controller=bpy.data.objects['BaiQi_Source_State_Controller'];states=json.loads(bpy.data.texts['BaiQi_Source_States.json'].as_string())['states'];scene=bpy.context.scene
scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX';scene.world=bpy.data.worlds.new('BaiQi component state studio');scene.world.color=(.1,.1,.1)
for loc,energy,size in [((180,-330,340),2400000,250),((-260,-150,240),1300000,250),((0,260,340),1900000,250)]:
    data=bpy.data.lights.new('State softbox','AREA');data.energy=energy;data.size=size;obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.location=loc;obj.rotation_euler=(Vector((0,0,148))-obj.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('BaiQi state camera');cam=bpy.data.objects.new(data.name,data);scene.collection.objects.link(cam);scene.camera=cam;data.type='ORTHO';data.clip_end=10000;records=[]
for state in states:
    controller['source_state']=state['index'];controller.update_tag();scene.frame_set(state['index']+1);bpy.context.view_layer.update()
    for name,scale,target,loc in [('head_front',68,(0,3,176),(0,-500,178)),('body_oblique',225,(0,3,103),(230,-470,103))]:
        data.ortho_scale=scale;cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();path=out/(f"{state['index']:02}_"+name+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
        records.append({'state':state['id'],'index':state['index'],'view':name,'path':path.relative_to(out).as_posix()})
    print('BAIQI_STATE_RENDERED',state['index'],state['id'],flush=True)
controller['source_state']=0;controller.update_tag();scene.frame_set(1);bpy.context.view_layer.update()
(out/'variant_render_manifest.json').write_text(json.dumps({'character':'白绮','model_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),'images':records,'status':'pending_visual_review','game_runtime_allowed':False},ensure_ascii=False,indent=2),encoding='utf-8');bpy.ops.wm.save_as_mainfile(filepath=str(out/'BaiQi_VariantReview.blend'))
