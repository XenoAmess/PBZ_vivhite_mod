"""Assemble BaiQi head components on the female foundation for review.

Original atlas UVs, masks and component identities are preserved. Face layers
are temporary projection surfaces for later baking, not accepted topology.
"""
import hashlib,json,math,sys
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/live2d_delta/baiqi_head_prototype_001';OUT.mkdir(parents=True,exist_ok=True)
source=json.loads((ROOT/'repro/baiqi_source/core_geometry.json').read_text(encoding='utf-8'));r=json.loads((ROOT/'artifacts/baiqi_component_audit/source_render_manifest.json').read_text(encoding='utf-8'));mvp=np.array(r['source_mvp']).reshape(4,4).T
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'output/live2d_delta/anatomy_foundation_002/Delta_adult.blend'));base=next(o for o in bpy.data.objects if o.type=='MESH');arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');base.name='BaiQi_FemaleFoundation'
for material in base.data.materials:material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.88,.76,.68,1)
coords=[base.matrix_world@v.co for v in base.data.vertices];faces=[list(p.vertices) for p in base.data.polygons if all(coords[i].z>160 for i in p.vertices)]
tree=BVHTree.FromPolygons(coords,faces)
root=bpy.data.collections.new('BaiQi_Original_Components');bpy.context.scene.collection.children.link(root);collections={p['id']:bpy.data.collections.new('BaiQi_'+p['id']+'__'+p['source_name']) for p in source['parts']}
for p in source['parts']:
    parent=collections[p['parent']] if p['parent'] else root;parent.children.link(collections[p['id']])
parts={p['id']:p for p in source['parts']}
def descendants(name):
    result={name}
    for child in parts[name]['children']:result.update(descendants(child))
    return result
head_parts=descendants('Head')|{'Bhair'};hair_parts=descendants('Hair')|{'Bhair','Mhair'}|descendants('Ponytail');dress_parts=descendants('Headdress')
atlas=bpy.data.images.load(str(ROOT/source['textures'][0]['path']),check_existing=True);atlas.pack()
mask_paths={tuple(i['mask_drawables']):ROOT/i['path'] for i in json.loads((ROOT/'artifacts/baiqi_component_audit/masks/manifest.json').read_text(encoding='utf-8'))}
materials={}
def material_for(d):
    key=(tuple(d['masks']),bool(d['constant_flags']&8),round(d['opacity'],5))
    if key in materials:return materials[key]
    mat=bpy.data.materials.new('BaiQi_source_'+str(len(materials)));mat.use_nodes=True;mat.surface_render_method='DITHERED';mat.use_backface_culling=False
    nodes=mat.node_tree.nodes;links=mat.node_tree.links;bsdf=nodes['Principled BSDF'];bsdf.inputs['Roughness'].default_value=.85
    uv=nodes.new('ShaderNodeUVMap');uv.uv_map='OriginalAtlas';tex=nodes.new('ShaderNodeTexImage');tex.image=atlas;links.new(uv.outputs['UV'],tex.inputs['Vector']);links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
    opacity=nodes.new('ShaderNodeMath');opacity.operation='MULTIPLY';opacity.inputs[1].default_value=d['opacity'];links.new(tex.outputs['Alpha'],opacity.inputs[0]);alpha=opacity.outputs[0]
    if d['masks']:
        image=bpy.data.images.load(str(mask_paths[tuple(d['masks'])]),check_existing=True);image.pack();mask=nodes.new('ShaderNodeTexImage');mask.image=image;canvas=nodes.new('ShaderNodeUVMap');canvas.uv_map='OriginalCanvas';links.new(canvas.outputs['UV'],mask.inputs['Vector']);mask_alpha=mask.outputs['Alpha']
        if d['constant_flags']&8:
            invert=nodes.new('ShaderNodeMath');invert.operation='SUBTRACT';invert.inputs[0].default_value=1;links.new(mask_alpha,invert.inputs[1]);mask_alpha=invert.outputs[0]
        product=nodes.new('ShaderNodeMath');product.operation='MULTIPLY';links.new(alpha,product.inputs[0]);links.new(mask_alpha,product.inputs[1]);alpha=product.outputs[0]
    links.new(alpha,bsdf.inputs['Alpha']);materials[key]=mat;return mat
def pixel(point):
    p=mvp@np.array([point[0],point[1],0,1]);return (p[0]/p[3]+1)*700,(1-p[1]/p[3])*1100
scale=195/1607
profile=[(160.5,8.8,8.8,7),(165,11.5,11.2,7),(172,13.4,13.3,7),(180,14.0,13.8,7),
    (186,13.5,12.5,6.5),(190,12.0,10.5,6),(193,9.8,8.0,5.5),(195,6.4,5.0,5.4),(196.8,.4,.4,5.4)]
def hair_point(x,z,back=False):
    rx,ry,cy=[float(np.interp(z,[p[0] for p in profile],[p[i] for p in profile])) for i in [1,2,3]]
    depth=ry*math.sqrt(max(.02,1-(x/max(.1,rx))**2));return cy+(depth if back else -depth)
created=[]
for d in source['drawables']:
    if d['part'] not in head_parts:continue
    bm=bmesh.new();uv=bm.loops.layers.uv.new('OriginalAtlas');canvas=bm.loops.layers.uv.new('OriginalCanvas');vs=[]
    for xy in d['positions_xy']:
        px,py=pixel(xy);vs.append(bm.verts.new(((px-694.5)*scale,0,165.35+(600-py)*scale)))
    for offset in range(0,len(d['indices']),3):
        ids=d['indices'][offset:offset+3]
        if len(set(ids))<3:continue
        try:f=bm.faces.new([vs[i] for i in ids])
        except ValueError:continue
        for loop,i in zip(f.loops,ids):
            loop[uv].uv=d['uvs'][i];px,py=pixel(d['positions_xy'][i]);loop[canvas].uv=(px/1400,1-py/2200)
    bmesh.ops.subdivide_edges(bm,edges=list(bm.edges),cuts=1,use_grid_fill=True)
    for v in bm.verts:
        x,z=v.co.x,v.co.z
        if d['part'] in hair_parts:v.co.y=hair_point(x,z,back=d['part']=='Bhair')-.18
        elif d['part'] in dress_parts:v.co.y=5.5-.1*(abs(x)-12)+.012*(x*x)-.12
        else:
            hit=tree.ray_cast(Vector((x,-100,z)),Vector((0,1,0)),300)[0]
            if hit is None:hit=tree.find_nearest(Vector((x,-3,z)))[0]
            v.co.y=(hit.y if hit is not None else -3)-.05-.001*d['render_order']
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));data=bpy.data.meshes.new('BaiQi_'+d['id']);bm.to_mesh(data);bm.free();obj=bpy.data.objects.new('BaiQi_'+d['part']+'__'+d['id'],data);collections[d['part']].objects.link(obj)
    obj.data.materials.append(material_for(d));obj.parent=arm;obj.vertex_groups.new(name='head').add(list(range(len(data.vertices))),1.,'REPLACE');mod=obj.modifiers.new('Adult native head','ARMATURE');mod.object=arm;mod.use_deform_preserve_volume=False
    for p in data.polygons:p.use_smooth=True
    obj['baiqi_source_part']=d['part'];obj['baiqi_source_drawable']=d['id'];obj['migration_status']='projection_prototype_not_accepted';obj.hide_render=d['opacity']<.001;obj.hide_set(d['opacity']<.001)
    created.append({'part':d['part'],'drawable':d['id'],'object':obj.name,'default_visible':d['opacity']>.001})
# A rounded scalp/back volume is independent of the face projection sheets.
bm=bmesh.new();rings=[]
for z,rx,ry,cy in profile:
    rings.append([bm.verts.new((rx*math.cos(2*math.pi*j/64),cy+ry*math.sin(2*math.pi*j/64),z)) for j in range(64)])
for i in range(1,len(rings)):
    for j in range(64):
        angle=2*math.pi*(j+.5)/64
        if math.sin(angle)<-.28 and profile[i][0]<187:continue
        f=bm.faces.new([rings[i-1][j],rings[i-1][(j+1)%64],rings[i][(j+1)%64],rings[i][j]]);f.smooth=True
bm.faces.new(rings[-1]);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));data=bpy.data.meshes.new('BaiQi rounded hair volume');bm.to_mesh(data);bm.free();obj=bpy.data.objects.new('BaiQi_Rounded_HairVolume',data);collections['Bhair'].objects.link(obj)
mat=bpy.data.materials.new('BaiQi inferred side hair');mat.use_nodes=True;mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.69,.75,.85,1);mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.8;data.materials.append(mat);obj.parent=arm;obj.vertex_groups.new(name='head').add(list(range(len(data.vertices))),1.,'REPLACE');mod=obj.modifiers.new('Adult native head','ARMATURE');mod.object=arm
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'BaiQi_Head_Assembly.blend'))
report={'character':'白绮','base':'anatomy_foundation_002','native_rig_bones':len(arm.data.bones),'source_component_collections':len(collections),'head_projection_objects':created,
    'status':'head_projection_prototype_not_accepted','limits':['Face layers require baking and visual calibration','Hair side/back volume needs contour review','Body clothing and remaining accessories are not migrated','Original expression states are inventoried, not implemented as game controls']}
(OUT/'assembly_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('BAIQI_HEAD_ASSEMBLY_PROTOTYPE',len(created),flush=True)
