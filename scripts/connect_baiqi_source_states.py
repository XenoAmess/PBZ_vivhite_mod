"""Connect archived source appearances and accessory switches in Blender."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--candidate',default='output/live2d_delta/baiqi_full_assembly_004/BaiQi_Assembly.blend');p.add_argument('--output',default='output/live2d_delta/baiqi_component_assembly_001');args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=ROOT/args.output;out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/args.candidate));manifest=json.loads((ROOT/'artifacts/baiqi_component_audit/variant_atlases/manifest.json').read_text(encoding='utf-8'));indices={v['id']:v['index'] for v in manifest['states']}
controller=bpy.data.objects.new('BaiQi_Source_State_Controller',None);bpy.context.scene.collection.objects.link(controller);controller['source_state']=0;controller.id_properties_ui('source_state').update(min=0,max=26,description='Original BaiQi source presets; index table in BaiQi_Source_States.json')
controller['show_hand_ring']=False;controller['show_constellation']=False
def drive(owner,data_path,index,expression,prop='source_state'):
    f=owner.driver_add(data_path,index) if index is not None else owner.driver_add(data_path);d=f.driver;d.type='SCRIPTED';v=d.variables.new();v.name='state';v.type='SINGLE_PROP';v.targets[0].id=controller;v.targets[0].data_path='["'+prop+'"]';d.expression=expression
for item in manifest['images']:
    layer=item['layer'];material_name={'face':'BaiQi original face appearance','glasses':'BaiQi round gold glasses appearance','hair_front':'BaiQi bob front appearance','headdress':'BaiQi black gold headdress appearance'}[layer]
    mat=bpy.data.materials[material_name];n=mat.node_tree.nodes;l=mat.node_tree.links;tex=next(n for n in n if n.type=='TEX_IMAGE');image=bpy.data.images.load(str(ROOT/item['path']),check_existing=True);image.pack();tex.image=image;tex.extension='CLIP'
    uv=n.new('ShaderNodeUVMap');uv.uv_map='BaiQiCanvas';mul=n.new('ShaderNodeVectorMath');mul.operation='MULTIPLY';mul.inputs[1].default_value=(1400/440/6,2200/400/5,1);add=n.new('ShaderNodeVectorMath');add.operation='ADD';l.new(uv.outputs[0],mul.inputs[0]);l.new(mul.outputs[0],add.inputs[0]);l.new(add.outputs[0],tex.inputs['Vector'])
    drive(add.inputs[1],'default_value',0,'-480/440/6+(state%6)/6');drive(add.inputs[1],'default_value',1,'-1500/400/5+(4-floor(state/6))/5')
    mat['baiqi_state_layer']=layer
coat_index=indices['E-Body-Coat.exp3'];machine_index=indices['E-Machine-Open.exp3'];combo=indices['Machine_And_Screen'];pony_index=indices['E-Hair-Ponytail.exp3']
for obj in [o for o in bpy.data.objects if o.type=='MESH']:
    parts=set(json.loads(obj.get('baiqi_source_parts','[]')))
    if 'Coat' in parts or obj.name.startswith('BaiQi anatomical sleeve') or obj.name.startswith('BaiQi white sleeve cuff') or obj.name.startswith('BaiQi gold cuff edge'):
        drive(obj,'hide_render',None,'state=='+str(coat_index));drive(obj,'hide_viewport',None,'state=='+str(coat_index))
    if obj.name=='BaiQi optional ponytails':
        obj.hide_set(False);drive(obj,'hide_render',None,'state!='+str(pony_index));drive(obj,'hide_viewport',None,'state!='+str(pony_index))
    if obj.name=='BaiQi optional machine':
        obj.hide_set(False);drive(obj,'hide_render',None,f'state!={machine_index} and state!={combo}');drive(obj,'hide_viewport',None,f'state!={machine_index} and state!={combo}')
    if obj.name=='BaiQi optional hand_ring':
        obj.hide_set(False);drive(obj,'hide_render',None,'not state','show_hand_ring');drive(obj,'hide_viewport',None,'not state','show_hand_ring')
    if obj.name=='BaiQi optional constellation effect':
        obj.hide_set(False);drive(obj,'hide_render',None,'not state','show_constellation');drive(obj,'hide_viewport',None,'not state','show_constellation')
text=bpy.data.texts.new('BaiQi_Source_States.json');text.write(json.dumps(manifest,ensure_ascii=False,indent=2))
text=bpy.data.texts.new('BaiQi_Assembly_Status.txt');text.write('白绮女性基模迁移工程，未通过形体/动作/组件验收。Source_State_Controller 是 Blender 源状态预览，不是已经接入游戏的控制器。未绘制的侧后外观属于推断重建，需要复查。')
bpy.context.scene.frame_set(1);bpy.context.view_layer.update();path=out/'BaiQi_Assembly.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
(out/'state_binding.json').write_text(json.dumps({'character':'白绮','model_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'status':'source_states_connected_pending_visual_review','states':manifest['states'],'limitations':['Original alternate hand gestures are not yet authored','Some variants require source-specific geometry changes','Machine screen is not yet a separate implemented object','Controller is Blender-only; game controls not connected']},ensure_ascii=False,indent=2),encoding='utf-8');print('BAIQI_SOURCE_STATES_CONNECTED',len(manifest['states']),flush=True)
