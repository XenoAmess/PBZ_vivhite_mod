"""Fit the inferred Delta surface to the locally extracted adult Hun skeleton.

This produces a reviewable prototype, not cooked Unreal assets. The texture
projection and inferred back must be visually reviewed before game packaging.
Run with Blender --background --factory-startup --python this_file.py.
"""
import json
import math
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

ROOT = Path(__file__).resolve().parents[1]
VARIANT=sys.argv[sys.argv.index('--variant')+1] if '--variant' in sys.argv else 'adult'
ARM_SURFACE_WEIGHTS='--arm-surface-weights' in sys.argv
MAP_HANDS='--map-hands' in sys.argv
SEMANTIC_ARMS='--semantic-arms' in sys.argv
assert VARIANT in ['adult','young']
OUT = ROOT / ('output/live2d_delta/prototype' if VARIANT=='adult' else 'output/live2d_delta/young_prototype')
if '--output' in sys.argv:OUT=Path(sys.argv[sys.argv.index('--output')+1]).resolve()
assert OUT.is_relative_to(ROOT),'Candidate outputs must remain in the workspace'
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = ROOT / 'artifacts/live2d_reconstruction/Delta_shape.glb'
if '--shape' in sys.argv:SOURCE=Path(sys.argv[sys.argv.index('--shape')+1]).resolve()
VANILLA = ROOT / 'artifacts/extracted/HuaShira/Characters/Hero/Hero_Hun/SkinParts/Hun_Body_Simple.glb'
if VARIANT=='young':VANILLA=ROOT/'artifacts/extracted/original/HuaShira/Characters/Hero/Young_Hun/SkinParts/Hun_Young_Body.glb'
assert SOURCE.is_file() and VANILLA.is_file()
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(VANILLA), bone_heuristic='TEMPERANCE')
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
arm.name = 'Armature'
arm.data.name = 'Delta_Hun_Armature'
original = [o for o in bpy.data.objects if o.type == 'MESH']
reference_names = {b.name for b in arm.data.bones}
assert len(reference_names) == (264 if VARIANT=='adult' else 1207), f'Unexpected game body bone count: {len(reference_names)}'
required_weapon_bones = {'weapon_l_child','weapon_r_child','ik_weapon_l_child','ik_weapon_r_child'} if VARIANT=='adult' else set()
assert required_weapon_bones <= reference_names
original_vertex_data = []
for obj in original:
    group_names = {g.index:g.name for g in obj.vertex_groups}
    for v in obj.data.vertices:
        original_vertex_data.append((obj.matrix_world @ v.co,
             [(group_names[g.group],g.weight) for g in v.groups if group_names[g.group] in reference_names]))
tree = KDTree(len(original_vertex_data))
for i,(pos,_) in enumerate(original_vertex_data):
    tree.insert(pos,i)
tree.balance()
arm_trees={}
for side in ['l','r']:
    donors=[]
    for index,(_,influences) in enumerate(original_vertex_data):
        arm_weight=sum(w for name,w in influences if name.endswith('_'+side) and
                       any(k in name for k in ['upperarm','lowerarm','hand','thumb','index','middle','ring','pinky','wrist']))
        if arm_weight>.8:donors.append(index)
    arm_tree=KDTree(len(donors))
    for index in donors:arm_tree.insert(original_vertex_data[index][0],index)
    arm_tree.balance();arm_trees[side]=arm_tree
for obj in original:
    bpy.data.objects.remove(obj, do_unlink=True)

before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(SOURCE))
meshes = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
assert meshes
bpy.ops.object.select_all(action='DESELECT')
for o in meshes: o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.join()
mesh = bpy.context.object
mesh.name = 'Delta_Live2D_Reconstruction'
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
before_decimation = len(mesh.data.polygons)
if before_decimation > 50000:
    mod = mesh.modifiers.new('Prototype polygon budget', 'DECIMATE')
    mod.ratio = 50000 / before_decimation
    bpy.ops.object.modifier_apply(modifier=mod.name)
coords = np.array([v.co[:] for v in mesh.data.vertices], dtype=np.float64)
minimum, maximum = coords.min(axis=0), coords.max(axis=0)
height = 1.95 if VARIANT=='adult' else 1.65
source_scale=height/1.95
pixel_bbox = (326,341,1063,1948)
pixel_scale = height / (pixel_bbox[3]-pixel_bbox[1])
center_x = (pixel_bbox[0]+pixel_bbox[2])/2
coords[:,0] = (coords[:,0]-(minimum[0]+maximum[0])/2) * (737*pixel_scale)/(maximum[0]-minimum[0])
coords[:,1] = (coords[:,1]-(minimum[1]+maximum[1])/2) * height/(maximum[2]-minimum[2])
coords[:,2] = (coords[:,2]-minimum[2]) * height/(maximum[2]-minimum[2])
for v,p in zip(mesh.data.vertices,coords): v.co=p
mesh.data.update()

# Freeze the front projection before fitting the surface to the game skeleton.
texture_path=ROOT/'artifacts/live2d/Delta_projection_padded.png'
if not texture_path.is_file(): texture_path=ROOT/'artifacts/live2d/Delta_front.png'
image = bpy.data.images.load(str(texture_path))
image.name = 'Delta_original_Live2D_projection'
image.pack()
uv = mesh.data.uv_layers.new(name='Live2DFrontProjection')
for polygon in mesh.data.polygons:
    for loop_index in polygon.loop_indices:
        p=coords[mesh.data.loops[loop_index].vertex_index]
        uv.data[loop_index].uv=((p[0]/pixel_scale+center_x)/1400,
                               1-(1948-p[2]/pixel_scale)/2200)

def material(name,color):
    m=bpy.data.materials.new(name)
    m.diffuse_color=(*color,1)
    m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Roughness'].default_value=0.85
    return m
front=material('Delta_Live2D_Front',(.5,.5,.5))
tex=front.node_tree.nodes.new('ShaderNodeTexImage'); tex.image=image
front.node_tree.links.new(tex.outputs['Color'],front.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
emission=front.node_tree.nodes.new('ShaderNodeEmission')
emission.inputs['Strength'].default_value=1.
front.node_tree.links.new(tex.outputs['Color'],emission.inputs['Color'])
front.node_tree.links.new(emission.outputs[0],front.node_tree.nodes['Material Output'].inputs['Surface'])
back_hair=material('Delta_Inferred_Hair_Back',(.73,.81,.86))
back_coat=material('Delta_Inferred_Coat_Back',(.075,.068,.105))
back_skirt=material('Delta_Inferred_Skirt_Back',(.78,.80,.86))
back_stocking=material('Delta_Inferred_Stocking_Back',(.022,.023,.027))
back_boot=material('Delta_Inferred_Boot_Back',(.018,.035,.11))
back_skin=material('Delta_Inferred_Skin',(.86,.70,.61))
back_white=material('Delta_Inferred_White',(.80,.83,.86))
mesh.data.materials.clear()
for m in [front,back_hair,back_coat,back_skirt,back_stocking,back_boot,back_skin,back_white]: mesh.data.materials.append(m)
for p in mesh.data.polygons:
    p.use_smooth=True
    z=p.center.z/source_scale; x=abs(p.center.x)/source_scale; y=p.center.y/source_scale
    if x>.30 and .95<z<1.25:
        if z>1.19: p.material_index=7
        elif 1.105<z<1.145 and x>.34: p.material_index=2
        else: p.material_index=6
    elif p.normal.y < -.05: p.material_index=0
    elif x>.32 and .96<z<1.16: p.material_index=6
    elif x<.055 and 1.53<z<1.65 and y<.07: p.material_index=6
    elif z>1.58: p.material_index=1
    elif z>1.03: p.material_index=2
    elif .87<z<1.03 and .04<x<.17: p.material_index=6
    elif z>.96: p.material_index=3
    elif z>.19: p.material_index=4
    elif z<.095 and y<-.045: p.material_index=7
    else: p.material_index=5

def point(name):
    if name.startswith('palm_end_'):
        side=name[-1]
        last=point('middle_03_'+side);previous=point('middle_02_'+side)
        return last+(last-previous)*.65
    return np.array((arm.matrix_world @ arm.data.bones[name].head_local)[:])
def pixel_point(x,y,depth=0.): return np.array([(x-center_x)*pixel_scale,depth,(1948-y)*pixel_scale])
source={
 'pelvis':pixel_point(center_x,1105,.045),
 'spine_01':pixel_point(center_x,1040,.04),
 'spine_02':pixel_point(center_x,970,.04),
 'spine_03':pixel_point(center_x,900,.035),
 'spine_04':pixel_point(center_x,830,.035),
 'spine_05':pixel_point(center_x,750,.04),
 'neck_01':pixel_point(center_x,650,.035),
 'neck_02':pixel_point(center_x,615,.02),
 'head':pixel_point(center_x,592,.015)}
for side,sign in [('l',1),('r',-1)]:
    for name,x,y,d in [('upperarm',136,720,.03),('lowerarm',240,930,.015),
                       ('hand',310,1040,-.025),('thigh',68,1120,.04),
                       ('calf',78,1450,.045),('foot',96,1780,.04),('ball',96,1900,-.07)]:
        source[name+'_'+side]=pixel_point(center_x+sign*x,y,d)
    if '--elbow-x' in sys.argv or '--elbow-y' in sys.argv:
        elbow_x=float(sys.argv[sys.argv.index('--elbow-x')+1]) if '--elbow-x' in sys.argv else 240.
        elbow_y=float(sys.argv[sys.argv.index('--elbow-y')+1]) if '--elbow-y' in sys.argv else 930.
        source['lowerarm_'+side]=pixel_point(center_x+sign*elbow_x,elbow_y,.015)
    if MAP_HANDS:source['palm_end_'+side]=pixel_point(center_x+sign*350,1115,-.025)
    if SEMANTIC_ARMS:source['clavicle_'+side]=pixel_point(center_x+sign*72,715,.035)
segment_stretch={}
for side in ['l','r']:
    for a,b in [('upperarm','lowerarm'),('lowerarm','hand')]:
        start,end=a+'_'+side,b+'_'+side
        old_length=float(np.linalg.norm(source[end]-source[start]))
        target_length=float(np.linalg.norm(point(end)-point(start)))
        segment_stretch[start]={'source_length_m':old_length,'target_length_m':target_length,'ratio':target_length/old_length}
segments=[('pelvis','spine_01'),('spine_01','spine_02'),('spine_02','spine_03'),
          ('spine_03','spine_04'),('spine_04','spine_05'),('spine_05','neck_01'),
          ('neck_01','neck_02'),('neck_02','head')]
for side in ['l','r']:
    segments += [(n+'_'+side,c+'_'+side) for n,c in [('upperarm','lowerarm'),('lowerarm','hand'),
                                                               ('thigh','calf'),('calf','foot'),('foot','ball')]]
    if MAP_HANDS:segments.append(('hand_'+side,'palm_end_'+side))
    if SEMANTIC_ARMS:segments.append(('clavicle_'+side,'upperarm_'+side))
distances=[]; transformed=[]
for name,child in segments:
    a,b=source[name],source[child]
    ta,tb=point(name),point(child)
    axis=b-a; length=np.linalg.norm(axis); direction=axis/length
    target_axis=tb-ta; target_length=np.linalg.norm(target_axis); target_direction=target_axis/target_length
    rotate=Vector(direction).rotation_difference(Vector(target_direction)).to_matrix()
    rotate=np.array(rotate)
    offset=coords-a
    parameter=offset@direction
    closest=a+np.clip(parameter,0,length)[:,None]*direction
    distances.append(np.linalg.norm(coords-closest,axis=1))
    radial=offset-parameter[:,None]*direction
    transformed.append(ta + radial@rotate.T + (parameter*target_length/length)[:,None]*target_direction)
distances=np.array(distances).T
nearest=np.argsort(distances,axis=1)[:,:4]
# A continuous field avoids seams at changes in the three nearest segments.
weights=1/np.maximum(distances,.04)**4
original_fit_weights=weights/weights.sum(axis=1,keepdims=True)
arm_ownership=None
if SEMANTIC_ARMS:
    # Use Cubism's actual Arm/Hand/Sleeve parts rather than inferring
    # ownership from distance to a bone. Coat sides are close to the arm.
    ownership_image=np.load(ROOT/'artifacts/live2d/arm_ownership.npy')
    px=np.clip(np.rint(coords[:,0]/pixel_scale+center_x).astype(int),0,1399)
    py=np.clip(np.rint(1948-coords[:,2]/pixel_scale).astype(int),0,2199)
    arm_ownership=ownership_image[py,px]
    arm_columns=[];body_columns=[]
    for j,(name,_) in enumerate(segments):
        if name.startswith(('upperarm_','lowerarm_','hand_')):
            correct_side=(coords[:,0]>0) if name.endswith('_l') else (coords[:,0]<0)
            weights[:,j]*=correct_side;arm_columns.append(j)
        else:body_columns.append(j)
    weights[:,arm_columns]*=arm_ownership[:,None]/np.maximum(weights[:,arm_columns].sum(axis=1,keepdims=True),1e-20)
    weights[:,body_columns]*=(1-arm_ownership[:,None])/np.maximum(weights[:,body_columns].sum(axis=1,keepdims=True),1e-20)
weights/=weights.sum(axis=1,keepdims=True)
nearest=np.argsort(weights,axis=1)[:,-4:]
transformed=np.array(transformed).transpose(1,0,2)
fitted=(transformed*weights[:,:,None]).sum(axis=1)
if SEMANTIC_ARMS:
    prior=(transformed*original_fit_weights[:,:,None]).sum(axis=1)
    transition=np.clip((py-800)/100.,0,1)
    transition=transition*transition*(3-2*transition)
    fitted=prior*(1-transition[:,None])+fitted*transition[:,None]
groups={n:mesh.vertex_groups.new(name=n) for n,_ in segments}
groups['head']=mesh.vertex_groups.new(name='head')
surface_weight_count=0
for i,p in enumerate(coords):
    assignment=[(segments[j][0],float(weights[i,j])) for j in nearest[i] if weights[i,j]>.0001]
    if p[2]>1.57*source_scale:
        head_weight=float(np.clip((p[2]-1.57*source_scale)/(.08*source_scale),0,1))
        head_weight=head_weight*head_weight*(3-2*head_weight)
        fitted[i]=(1-head_weight)*fitted[i]+head_weight*(p+point('head')-source['head'])
        assignment=[(n,w*(1-head_weight)) for n,w in assignment if w*(1-head_weight)>.0001]
        assignment.append(('head',head_weight))
    # Reuse local game hand weighting when the inferred hand is close enough.
    if not ARM_SURFACE_WEIGHTS and abs(p[0])>.36*source_scale and p[2]<1.16*source_scale and p[2]>.96*source_scale:
        _,index,distance=tree.find(Vector(fitted[i]))
        if distance<.065:
            hand_weights=original_vertex_data[index][1]
            if hand_weights: assignment=hand_weights
    if ARM_SURFACE_WEIGHTS:
        side='l' if p[0]>0 else 'r'
        arm_influence=sum(w for n,w in assignment if n in ['upperarm_'+side,'lowerarm_'+side,'hand_'+side])
        if arm_influence>.5:
            # Transfer a smoothly averaged native anatomical surface, including
            # the game's twist bones, instead of guessing by 2D segment distance.
            donors=arm_trees[side].find_n(Vector(fitted[i]),6)
            transferred={}
            factor_sum=0.
            for _,index,distance in donors:
                factor=1/max(distance,.004)**2;factor_sum+=factor
                for name,w in original_vertex_data[index][1]:
                    transferred[name]=transferred.get(name,0.)+w*factor
            transferred={n:w/factor_sum for n,w in transferred.items()}
            # Avoid a sharp change where coat and shoulder meet.
            blend=float(np.clip((arm_influence-.5)/.35,0,1))
            combined={n:w*(1-blend) for n,w in assignment}
            for n,w in transferred.items():combined[n]=combined.get(n,0.)+w*blend
            assignment=sorted(((n,w) for n,w in combined.items() if w>.0001),key=lambda item:-item[1])[:8]
            surface_weight_count+=1
    total=sum(w for _,w in assignment)
    for name,w in assignment:
        if name not in groups: groups[name]=mesh.vertex_groups.new(name=name)
        groups[name].add([i],w/total,'REPLACE')
    mesh.data.vertices[i].co=fitted[i]
mesh.data.update()
if SEMANTIC_ARMS:
    # Smooth the native transfer on the actual sleeve surface. A closest
    # donor can jump across an elbow fold, producing abrupt bone weights.
    group_list=list(mesh.vertex_groups)
    matrix=np.zeros((len(mesh.data.vertices),len(group_list)),dtype=np.float32)
    for v in mesh.data.vertices:
        for g in v.groups:matrix[v.index,g.group]=g.weight
    topology=np.array([e.vertices[:] for e in mesh.data.edges])
    same_arm=(arm_ownership[topology[:,0]]>.01)&(arm_ownership[topology[:,1]]>.01)
    a,b=topology[same_arm].T
    degree=np.bincount(np.r_[a,b],minlength=len(matrix)).astype(np.float32)
    selected=degree>0
    for iteration in range(12):
        total=np.zeros_like(matrix)
        np.add.at(total,a,matrix[b]);np.add.at(total,b,matrix[a])
        matrix[selected]=matrix[selected]*.4+total[selected]/degree[selected,None]*.6
    arm_columns=[g.index for g in group_list if any(k in g.name for k in ['upperarm','lowerarm','hand','thumb','index','middle','ring','pinky','wrist'])]
    body_columns=[g.index for g in group_list if g.index not in arm_columns]
    matrix[:,arm_columns]*=arm_ownership[:,None]/np.maximum(matrix[:,arm_columns].sum(axis=1,keepdims=True),1e-20)
    matrix[:,body_columns]*=(1-arm_ownership[:,None])/np.maximum(matrix[:,body_columns].sum(axis=1,keepdims=True),1e-20)
    # Sleeve cloth and its ribbon follow the main upper arm, not the native
    # muscle correctives. Fade into native elbow/forearm weights gradually.
    sleeve=np.clip((915-py)/80.,0,1)
    sleeve=sleeve*sleeve*(3-2*sleeve)
    matrix[:,arm_columns]*=1-sleeve[:,None]
    for side,positive in [('l',True),('r',False)]:
        rows=(coords[:,0]>0) if positive else (coords[:,0]<0)
        matrix[rows,groups['upperarm_'+side].index]+=arm_ownership[rows]*sleeve[rows]
    selected|=(arm_ownership>.001)
    for i in np.where(selected)[0]:
        order=np.argsort(matrix[i])[-8:];values=matrix[i,order];values/=values.sum()
        for g in mesh.vertex_groups:g.remove([int(i)])
        for index,value in zip(order,values):
            if value>.0001:group_list[int(index)].add([int(i)],float(value),'REPLACE')
    for v in mesh.data.vertices:
        total=sum(g.weight for g in v.groups)
        for g in list(v.groups):mesh.vertex_groups[g.group].add([v.index],g.weight/total,'REPLACE')
hand_repair=None
if '--repair-hands' in sys.argv:
    sys.path.insert(0,str(ROOT/'scripts'))
    from delta_hands import repair_hands
    hand_repair=repair_hands(mesh,arm)
    back_skin.diffuse_color=(.93,.84,.78,1.)
    back_skin.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=back_skin.diffuse_color
edge_ratios=[]
for e in ([] if hand_repair else mesh.data.edges):
    a,b=e.vertices
    edge_ratios.append(float(np.linalg.norm(fitted[a]-fitted[b])/max(np.linalg.norm(coords[a]-coords[b]),1e-8)))
mesh.parent=arm
skin=mesh.modifiers.new('Hun game skeleton','ARMATURE');skin.object=arm
arm.show_in_front=True
arm['source_game_build']='26367565'
arm['warning']='Bone names/hierarchy verified; cooked bind rotations and runtime still require validation'
mesh['source']='Delta.zip only; full.jpg excluded'
mesh['stage']='Reconstructed and approximately fitted prototype; not a finished Mod'

# Keep an editable project, export only the candidate, and never include game meshes.
bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);mesh.select_set(True)
bpy.context.view_layer.objects.active=arm
scene=bpy.context.scene
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Delta_live2d.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'Delta_live2d.glb'),use_selection=True,
                          export_format='GLB',export_animations=False,export_all_influences=False)
# FBX uses a Principled material wrapper; export its portable texture explicitly.
front.node_tree.links.new(front.node_tree.nodes['Principled BSDF'].outputs[0],front.node_tree.nodes['Material Output'].inputs['Surface'])
bpy.ops.export_scene.fbx(filepath=str(OUT/'Delta_live2d.fbx'),use_selection=True,
                         object_types={'ARMATURE','MESH'},add_leaf_bones=False,
                         bake_anim=False,armature_nodetype='NULL',use_armature_deform_only=False,
                         axis_forward='-Y',axis_up='Z',path_mode='COPY',embed_textures=True)
front.node_tree.links.new(emission.outputs[0],front.node_tree.nodes['Material Output'].inputs['Surface'])
report={'status':'prototype_only','source':'Delta.zip','full_jpg_used':False,'variant':VARIANT,
 'shape_file':str(SOURCE.relative_to(ROOT)),
 'game_build':'26367565','bone_count':len(arm.data.bones),'bone_names':sorted(reference_names),
 'weapon_bones_preserved':sorted(required_weapon_bones),
 'vertices':len(mesh.data.vertices),'triangles':sum(len(p.vertices)-2 for p in mesh.data.polygons),
 'generated_faces_before_decimation':before_decimation,
 'unweighted_vertices':sum(not v.groups for v in mesh.data.vertices),
 'arm_segment_stretch':segment_stretch,
 'arm_surface_weight_vertices':surface_weight_count,'explicit_hand_fit':MAP_HANDS,
 'semantic_cubism_arm_mask':SEMANTIC_ARMS,
 'hand_repair':hand_repair,
 'fit_edge_length_ratio_p99':float(np.percentile(edge_ratios,99)) if edge_ratios else None,
 'fit_edge_length_ratio_max':float(max(edge_ratios)) if edge_ratios else None,
 'limitations':['Single-view shape inference; back and sides are inferred',
 'Front texture uses original Live2D art; back uses provisional flat materials',
 'Skin weights and fit are preliminary; no facial blendshapes or cloth yet',
 'Exact cooked skeleton transforms have not been compared',
 'No UE cooking, no game containers, no runtime validation']}
(OUT/'candidate_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

# Multi-view renders make the limitations directly reviewable.
scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=900;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
if scene.world is None:
    scene.world=bpy.data.worlds.new('Delta Studio World')
scene.world.color=(.18,.18,.18)
scene.view_settings.view_transform='Standard'
for loc,energy,size in [((3,-4,5),650,4),((-3,-1,3),350,3),((0,3,4),500,3)]:
    data=bpy.data.lights.new('Studio area','AREA');data.energy=energy;data.shape='DISK';data.size=size
    light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light);light.location=loc
    light.rotation_euler=(Vector((0,0,1.))-light.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('Review camera');camera=bpy.data.objects.new('Review camera',data)
scene.collection.objects.link(camera);scene.camera=camera;data.type='ORTHO';data.ortho_scale=2.55
for name,location in [('front',(0,-5,1.05)),('three_quarter',(3,-4,1.15)),('side',(5,0,1.05)),('back',(0,5,1.05))]:
    camera.location=location
    camera.rotation_euler=(Vector((0,0,1.04))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/f'preview_{name}.png');bpy.ops.render.render(write_still=True)
print('CANDIDATE_READY',json.dumps({k:v for k,v in report.items() if k!='bone_names'}))
