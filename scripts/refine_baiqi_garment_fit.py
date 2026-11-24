"""Repair shoulder coverage, rear-hair UVs and the actual neutral sole level."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--candidate',default='output/live2d_delta/baiqi_component_assembly_008/BaiQi_Assembly.blend');p.add_argument('--output',default='output/live2d_delta/baiqi_component_assembly_009');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=ROOT/a.output;out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/a.candidate));base=bpy.data.objects['BaiQi_FemaleFoundation'];arm=base.parent;ctrl=bpy.data.objects['BaiQi_Source_State_Controller'];scale=195/1607
# A body-neck face must not inherit the projected facial outline.
source=base.data.attributes['anatomy_source_object'];skin_slot=next(i for i,m in enumerate(base.data.materials) if m.name=='BaiQi Skin')
for poly in base.data.polygons:
    if source.data[poly.index].value==0 and poly.center.z>160:poly.material_index=skin_slot
# Keep the source hair pigment inside the rear source silhouette. Sampling a
# silhouette line as a surface texture creates a spurious loop on the temple.
image=bpy.data.images.load(str(ROOT/'artifacts/baiqi_component_audit/head_layers/hair_back.png'),check_existing=True);arr=np.empty(len(image.pixels),dtype=np.float32);image.pixels.foreach_get(arr);mask=arr.reshape(2200,1400,4)[::-1,:,3]>.5
for obj in [o for o in bpy.data.objects if o.name.startswith('BaiQi rear hair clump')]:
    uv=obj.data.uv_layers['BaiQiCanvas']
    for loop in obj.data.loops:
        co=obj.data.vertices[loop.vertex_index].co;py=int(np.clip(600-(co.z-165.35)/scale,355,610));xs=np.flatnonzero(mask[py]);lo,hi=(xs[0],xs[-1]) if len(xs)>1 else (690,700)
        u=(float(lo+hi)/2+float(hi-lo)*.40*float(np.clip(co.x/15.5,-1,1)))/1400;uv.data[loop.index].uv=(u,1-py/2200)
# The coat needs a fitted shoulder/underarm continuation with the same native
# skin weights as the female body, rather than a gap between cut arm pieces.
mat=bpy.data.materials['BaiQi inferred rear coat']
for side in ['l','r']:
    obj=base.copy();obj.data=base.data.copy();obj.name='BaiQi fitted shoulder coverage '+side;bpy.context.scene.collection.objects.link(obj);bm=bmesh.new();bm.from_mesh(obj.data);tag=bm.faces.layers.int['anatomy_source_object'];surf=bm.faces.layers.int['anatomy_source_material'];sign=1 if side=='l' else -1
    keep=lambda f:f[tag]==0 and f[surf]==0 and all(12<sign*v.co.x<35 and 135<v.co.z<159 for v in f.verts)
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if not keep(f)],context='FACES');bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS');bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    for v in bm.verts:v.co+=v.normal*.70
    bm.to_mesh(obj.data);bm.free();obj.data.materials.clear();obj.data.materials.append(mat)
    for poly in obj.data.polygons:poly.material_index=0;poly.use_smooth=True
    obj['baiqi_source_parts']=json.dumps(['Coat','Part39' if side=='l' else 'Part38']);obj['migration_status']='fit_repair_pending_review'
    for name in ['hide_render','hide_viewport']:
        d=obj.driver_add(name).driver;v=d.variables.new();v.name='state';v.targets[0].id=ctrl;v.targets[0].data_path='["source_state"]';d.expression='state==1'
    assert len([m for m in obj.modifiers if m.type=='ARMATURE' and m.object==arm])==1
shoes=bpy.data.objects['BaiQi boot foundation'];before=min(v.co.z for v in shoes.data.vertices);target=json.loads((ROOT/'artifacts/native_reference_bounds.json').read_text(encoding='utf-8'))
# The selected native reference report has a stable measured minimum.
floor=target['foot_vertices_z_min'];offset=floor-before
for v in shoes.data.vertices:v.co.z+=offset
path=out/'BaiQi_Assembly.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path));(out/'fit_report.json').write_text(json.dumps({'status':'pending_visual_review','source_candidate':a.candidate,'model_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'shoe_floor_before_cm':before,'shoe_floor_after_cm':floor,'shoe_vertical_offset_cm':offset,'repairs':['body neck no longer samples facial outline','rear hair UV no longer samples source silhouette border','native-weighted shoulder coverage','sole aligned to measured original adult reference']},indent=2));print('BAIQI_GARMENT_FIT_REPAIRS_READY',flush=True)
