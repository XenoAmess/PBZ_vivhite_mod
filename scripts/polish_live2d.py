"""Improve rear color continuity without changing any pose or vertex weight."""
import json
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'output/live2d_delta/hunyuan21_semantic'
OUT=ROOT/'output/live2d_delta/hunyuan21_polished';OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE/'Delta_live2d.blend'))
mesh=next(o for o in bpy.data.objects if o.type=='MESH')
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
image=bpy.data.images.load(str(ROOT/'artifacts/live2d/Delta_back_inferred.png'));image.pack()
for mat in mesh.data.materials:
    if mat.name=='Delta_Live2D_Front':continue
    bs=mat.node_tree.nodes.get('Principled BSDF')
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image
    mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value=.95
tree=BVHTree.FromPolygons([v.co for v in mesh.data.vertices],[p.vertices for p in mesh.data.polygons])
reassigned=0
uv=mesh.data.uv_layers.active
for polygon in mesh.data.polygons:
    # A rear-facing fold can have a locally forward normal. It must not inherit
    # front clothing/face pixels merely because of that normal.
    if polygon.material_index==0:
        c=polygon.center
        hit,_,_,_=tree.ray_cast(Vector((c.x,-3.,c.z)),Vector((0,1,0)))
        if hit is not None and abs(hit.y-c.y)>.006:
            polygon.material_index=2;reassigned+=1
    # Procedural palm/finger faces use a constant UV rather than the Live2D
    # projection. Move those faces to the explicitly reserved skin swatch.
    if polygon.material_index==6 and all((uv.data[i].uv-Vector((.70,.51))).length<.0001 for i in polygon.loop_indices):
        for i in polygon.loop_indices:uv.data[i].uv=(.99,.01)
mesh['rear_texture']='Procedurally inferred from Delta only; no rear reference was supplied'
import sys
sys.path.insert(0,str(ROOT/'scripts'))
from delta_surface_normals import soften_face_normals
face_corners=soften_face_normals(mesh)
mesh['face_lighting_normal_corners']=face_corners
bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);arm.select_set(True)
bpy.context.view_layer.objects.active=arm
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Delta_live2d.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'Delta_live2d.glb'),use_selection=True,export_format='GLB',export_animations=False,export_all_influences=True)
front=mesh.data.materials['Delta_Live2D_Front']
output=front.node_tree.nodes['Material Output'].inputs['Surface']
emission=next(n for n in front.node_tree.nodes if n.type=='EMISSION')
front.node_tree.links.new(front.node_tree.nodes['Principled BSDF'].outputs[0],output)
bpy.ops.export_scene.fbx(filepath=str(OUT/'Delta_live2d.fbx'),use_selection=True,object_types={'ARMATURE','MESH'},
    add_leaf_bones=False,bake_anim=False,armature_nodetype='NULL',axis_forward='-Y',axis_up='Z',path_mode='COPY',embed_textures=True)
front.node_tree.links.new(emission.outputs[0],output)
report=json.loads((SOURCE/'candidate_report.json').read_text())
report['rear_texture']='artifacts/live2d/Delta_back_inferred.png'
report['rear_fold_faces_reassigned']=reassigned
report['geometry_and_weights_changed']=False
(OUT/'candidate_report.json').write_text(json.dumps(report,indent=2))
# Save the same four studio views used for the preceding candidate.
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=900;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.view_settings.view_transform='Standard'
if scene.world is None:scene.world=bpy.data.worlds.new('Delta Studio')
scene.world.color=(.18,.18,.18)
for location,energy in [((3,-4,5),650),((-3,-1,3),350),((0,3,4),500)]:
    light=bpy.data.lights.new('Review','AREA');light.energy=energy;light.shape='DISK';light.size=4
    obj=bpy.data.objects.new('Review',light);scene.collection.objects.link(obj);obj.location=location
    obj.rotation_euler=(Vector((0,0,1))-obj.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('Review');camera=bpy.data.objects.new('Review',data);scene.collection.objects.link(camera)
scene.camera=camera;data.type='ORTHO';data.ortho_scale=2.55
for name,location in [('front',(0,-5,1.05)),('back',(0,5,1.05)),('side',(5,0,1.05)),('three_quarter',(3,-4,1.15))]:
    camera.location=location;camera.rotation_euler=(Vector((0,0,1.04))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/f'preview_{name}.png');bpy.ops.render.render(write_still=True)
print('REAR_COLOR_CONTINUITY_READY',reassigned)
