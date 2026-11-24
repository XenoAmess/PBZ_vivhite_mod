"""Unify fitted source hair surfaces into one continuous three-dimensional bob."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--candidate',default='output/live2d_delta/baiqi_component_assembly_002/BaiQi_Assembly.blend');p.add_argument('--output',default='output/live2d_delta/baiqi_component_assembly_003');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=ROOT/a.output;out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/a.candidate));arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');hair=[o for o in bpy.data.objects if o.type=='MESH' and (o.name in ['BaiQi bob front','BaiQi rounded rear hair'] or o.name.startswith('BaiQi side hair continuation'))];assert len(hair)==4
before={b.name:(list(b.matrix_local),b.parent.name if b.parent else None) for b in arm.data.bones}
bpy.ops.object.select_all(action='DESELECT');source_parts=set()
for o in hair:
    source_parts.update(json.loads(o.get('baiqi_source_parts','[]')))
    for m in o.modifiers:
        if m.type=='SOLIDIFY':m.thickness=.72;m.offset=0
    if not any(m.type=='SOLIDIFY' for m in o.modifiers):m=o.modifiers.new('Closed hair volume','SOLIDIFY');m.thickness=.72;m.offset=0
    o.select_set(True)
bpy.context.view_layer.objects.active=hair[0];bpy.ops.object.convert(target='MESH');bpy.ops.object.join();obj=bpy.context.object;obj.name='BaiQi unified bob volume';obj.modifiers.clear();m=obj.modifiers.new('Continuous hair voxel union','REMESH');m.mode='VOXEL';m.voxel_size=.16;m.use_smooth_shade=True;bpy.ops.object.modifier_apply(modifier=m.name)
m=obj.modifiers.new('Hair surface relaxation','SMOOTH');m.factor=.35;m.iterations=5;bpy.ops.object.modifier_apply(modifier=m.name)
front=bpy.data.materials['BaiQi bob front appearance'];n=front.node_tree.nodes;l=front.node_tree.links;bsdf=n['Principled BSDF'];tex=next(n for n in n if n.type=='TEX_IMAGE')
for link in list(bsdf.inputs['Alpha'].links):l.remove(link)
bsdf.inputs['Alpha'].default_value=1
mix=n.new('ShaderNodeMixRGB');mix.inputs[1].default_value=(.72,.80,.85,1);l.new(tex.outputs['Alpha'],mix.inputs[0]);l.new(tex.outputs['Color'],mix.inputs[2]);l.new(mix.outputs[0],bsdf.inputs['Base Color'])
back=bpy.data.materials['BaiQi side hair source color'];obj.data.materials.clear();obj.data.materials.append(front);obj.data.materials.append(back)
uv=obj.data.uv_layers.get('BaiQiCanvas') or obj.data.uv_layers.new(name='BaiQiCanvas');scale=195/1607
for poly in obj.data.polygons:
    poly.material_index=0 if poly.center.y<6.5 else 1;poly.use_smooth=True
    for li in poly.loop_indices:
        co=obj.data.vertices[obj.data.loops[li].vertex_index].co;uv.data[li].uv=((co.x/scale+694.5)/1400,1-(600-(co.z-165.35)/scale)/2200)
obj.vertex_groups.clear();obj.vertex_groups.new(name='head').add(list(range(len(obj.data.vertices))),1,'REPLACE');obj.parent=arm;m=obj.modifiers.new('Native adult head linear skin','ARMATURE');m.object=arm;obj['baiqi_source_parts']=json.dumps(sorted(source_parts));obj['migration_status']='unified_hair_pending_visual_review'
# Smooth the artificial waist step left by the first coat envelope.
coat=bpy.data.objects['BaiQi coat side back'];rings=80;columns=72;assert len(coat.data.vertices)==rings*columns
for _ in range(7):
    rows={i:coat.data.vertices[i].co.copy() for i in range(len(coat.data.vertices))}
    for i,v in enumerate(coat.data.vertices):
        row=i//columns
        if 125<v.co.z<140 and row>0 and row<rings-1:
            v.co.x=.5*rows[i].x+.25*(rows[i-columns].x+rows[i+columns].x);v.co.y=.5*rows[i].y+.25*(rows[i-columns].y+rows[i+columns].y)
assert len(arm.data.bones)==264
for b in arm.data.bones:assert before[b.name]==(list(b.matrix_local),b.parent.name if b.parent else None)
path=out/'BaiQi_Assembly.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path));(out/'hair_volume_report.json').write_text(json.dumps({'status':'pending_visual_review','source_candidate':a.candidate,'source_sha256':hashlib.sha256((ROOT/a.candidate).read_bytes()).hexdigest(),'model_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'hair_vertices':len(obj.data.vertices),'hair_polygons':len(obj.data.polygons),'native_bones_unchanged':True,'source_parts':sorted(source_parts)},indent=2));print('BAIQI_UNIFIED_HAIR_READY',len(obj.data.vertices),flush=True)
