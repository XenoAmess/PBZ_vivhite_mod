"""Physical casing, collar and individual source holographic accessories."""
import argparse,hashlib,json,math,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--candidate',default='output/live2d_delta/baiqi_component_assembly_005/BaiQi_Assembly.blend');p.add_argument('--output',default='output/live2d_delta/baiqi_component_assembly_006');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=ROOT/a.output;out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/a.candidate));arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');ctrl=bpy.data.objects['BaiQi_Source_State_Controller'];ctrl['constellation_phase']=0;ctrl.id_properties_ui('constellation_phase').update(min=0,max=5)
for name in ['BaiQi optional machine','BaiQi optional constellation effect']:bpy.data.objects.remove(bpy.data.objects[name],do_unlink=True)
layers=ROOT/'artifacts/baiqi_component_audit/optional_layers';scale=195/1607;records=[]
def drive(obj,expression,prop='source_state'):
    for name in ['hide_render','hide_viewport']:
        driver=obj.driver_add(name).driver;v=driver.variables.new();v.name='state';v.targets[0].id=ctrl;v.targets[0].data_path='["'+prop+'"]';driver.expression=expression
def make(layer,part,bone,depth,thickness=.12,energy=False):
    image=bpy.data.images.load(str(layers/(layer+'.png')),check_existing=True);image.pack();arr=np.empty(len(image.pixels),dtype=np.float32);image.pixels.foreach_get(arr);mask=arr.reshape(2200,1400,4)[::-1,:,3]>.12;ys,xs=np.nonzero(mask);vs=[];fs=[];uvs=[];lookup={};step=2
    if not len(xs):return None
    def vert(px,py):
        if (px,py) not in lookup:
            x=(px-694.5)*scale;z=165.35+(600-py)*scale;co=(x,depth(x,z),z);lookup[(px,py)]=len(vs);vs.append(co);uvs.append((px/1400,1-py/2200))
        return lookup[(px,py)]
    for py in range(max(0,int(ys.min())-step),min(2200-step,int(ys.max())+step),step):
        for px in range(max(0,int(xs.min())-step),min(1400-step,int(xs.max())+step),step):
            if mask[py:py+step+1,px:px+step+1].any():fs.append((vert(px,py),vert(px,py+step),vert(px+step,py+step),vert(px+step,py)))
    data=bpy.data.meshes.new('BaiQi '+layer);data.from_pydata(vs,[],fs);mat=bpy.data.materials.new('BaiQi '+layer+' original appearance');mat.use_nodes=True;mat.surface_render_method='DITHERED';n=mat.node_tree.nodes;l=mat.node_tree.links;b=n['Principled BSDF'];tex=n.new('ShaderNodeTexImage');tex.image=image;uv=n.new('ShaderNodeUVMap');uv.uv_map='BaiQiCanvas';l.new(uv.outputs[0],tex.inputs['Vector']);l.new(tex.outputs['Color'],b.inputs['Base Color']);l.new(tex.outputs['Alpha'],b.inputs['Alpha']);b.inputs['Roughness'].default_value=.8
    if energy:l.new(tex.outputs['Color'],b.inputs['Emission Color']);b.inputs['Emission Strength'].default_value=.4
    data.materials.append(mat);uv=data.uv_layers.new(name='BaiQiCanvas')
    for loop in data.loops:uv.data[loop.index].uv=uvs[loop.vertex_index]
    obj=bpy.data.objects.new(data.name,data);col=next(c for c in bpy.data.collections if c.name.startswith('BaiQi '+part+' '));col.objects.link(obj);obj.parent=arm;obj.vertex_groups.new(name=bone).add(list(range(len(data.vertices))),1,'REPLACE');mod=obj.modifiers.new('Native adult linear skin','ARMATURE');mod.object=arm
    if thickness:mod=obj.modifiers.new('Physical thickness cm','SOLIDIFY');mod.thickness=thickness;mod.offset=0
    obj['baiqi_source_parts']=json.dumps([part]);obj['migration_status']='assembled_pending_review';records.append({'object':obj.name,'source_parts':[part],'source_layer':layer,'representation':'holographic surface' if energy else 'solid three-dimensional surface'});return obj
for layer,part,thickness,energy in [('machine_core','Part2',2.2,False),('machine_wings','Part3',0,True),('machine_rings','Part4',0,True),('machine_screen','Part',0,True)]:
    obj=make(layer,part,'spine_05',lambda x,z:-2,thickness,energy)
    if obj:drive(obj,'state!=26' if layer=='machine_screen' else 'state!=21 and state!=26')
for index,name in enumerate(['S1','S2','S3','S4','ArtMesh53'],1):
    obj=make(name,'Part40','pelvis',lambda x,z:5-38*math.sqrt(max(.02,1-(x/57)**2-((z-75)/66)**2)),0,True)
    if obj:drive(obj,'state!='+str(index),'constellation_phase');obj['source_drawable']=name
make('shirt_collar','Collar','spine_05',lambda x,z:-1-(164-z)*.7-.08*x*x,.16)
# Retarget the source hand hologram to the actual adult hand rest landmarks.
obj=bpy.data.objects.get('BaiQi optional hand_ring');hand=arm.data.bones['hand_r'].head_local;finger=arm.data.bones['middle_03_r'].head_local;sa=np.array([(420-694.5)*scale,165.35+(600-1030)*scale]);se=np.array([(372-694.5)*scale,165.35+(600-1107)*scale]);sd=(se-sa)/np.linalg.norm(se-sa);td=np.array([finger.x-hand.x,finger.z-hand.z]);target_length=np.linalg.norm(td);td/=target_length
if obj:
    for v in obj.data.vertices:
        q=np.array([v.co.x,v.co.z])-sa;dst=np.array([hand.x,hand.z])+td*np.dot(q,sd)*target_length/np.linalg.norm(se-sa)+np.array([-td[1],td[0]])*np.dot(q,[-sd[1],sd[0]])
        v.co=(float(dst[0]),hand.y-3.8,float(dst[1]))
path=out/'BaiQi_Assembly.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path));(out/'accessory_report.json').write_text(json.dumps({'status':'pending_visual_review','model_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_candidate':a.candidate,'objects':records,'limits':['Holographic layers are intentional surfaces, not solid cloth','All appearance controls are Blender previews; not game controls','Alternate hand poses and collision review remain pending']},indent=2));print('BAIQI_OPTIONAL_ACCESSORIES',len(records),flush=True)
