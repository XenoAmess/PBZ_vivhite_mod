"""Render the user-selected native female models as anatomy references."""
import hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools/blender_libs'),str(ROOT/'vendor/UEFormat/plugins/blender')]
from io_scene_ueformat.importer.import_context import UEFormatImport
from io_scene_ueformat.options import UEModelOptions
source=ROOT/'artifacts/extracted/female_reference';out=ROOT/'artifacts/female_references';out.mkdir(exist_ok=True)
reports=[]
for character in ['YuEr','MuXiaoKui']:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    files={part:next(source.rglob(character+'_'+part+'.uemodel')) for part in ['Body','Head']}
    objects={}
    for part,path in files.items():
        before=set(bpy.data.objects);UEFormatImport(UEModelOptions(scale_factor=1.,reorient_bones=False,import_sockets=False,import_morph_targets=False)).import_file(path)
        objects[part]=list(set(bpy.data.objects)-before)
    body_arm=next(o for o in objects['Body'] if o.type=='ARMATURE');head_arm=next(o for o in objects['Head'] if o.type=='ARMATURE')
    alignment=None
    if 'head' in body_arm.data.bones and 'head' in head_arm.data.bones:
        a=body_arm.matrix_world@body_arm.data.bones['head'].matrix_local;b=head_arm.matrix_world@head_arm.data.bones['head'].matrix_local
        transform=a@b.inverted();alignment=[list(row) for row in transform]
        for obj in objects['Head']:
            if obj.parent is None:obj.matrix_world=transform@obj.matrix_world
    clay=bpy.data.materials.new('Reference clay');clay.use_nodes=True;clay.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.36,.4,.44,1);clay.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.85
    meshes=[o for o in bpy.data.objects if o.type=='MESH']
    for obj in meshes:
        obj.data.materials.clear();obj.data.materials.append(clay)
        for polygon in obj.data.polygons:polygon.material_index=0;polygon.use_smooth=True
    coords=np.concatenate([np.array([obj.matrix_world@v.co for v in obj.data.vertices]) for obj in meshes]);minimum,maximum=coords.min(axis=0),coords.max(axis=0);height=float(maximum[2]-minimum[2])
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
    scene.world=bpy.data.worlds.new('Reference studio');scene.world.color=(.1,.1,.1)
    for location,energy,size in [((180,-330,340),2400000,250),((-260,-150,240),1300000,250),((0,260,340),1900000,250)]:
        data=bpy.data.lights.new('Reference softbox','AREA');data.energy=energy;data.size=size;obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.location=location;obj.rotation_euler=(Vector((0,0,140))-obj.location).to_track_quat('-Z','Y').to_euler()
    data=bpy.data.cameras.new('Reference camera');cam=bpy.data.objects.new(data.name,data);scene.collection.objects.link(cam);scene.camera=cam;data.type='ORTHO';data.clip_end=10000
    folder=out/character;folder.mkdir(exist_ok=True);images=[]
    head=body_arm.matrix_world@body_arm.data.bones['head'].head_local if 'head' in body_arm.data.bones else Vector((0,0,float(maximum[2]-18)))
    for region,target,scale in [('body',Vector((0,0,float((minimum[2]+maximum[2])*.5))),height*1.15),('head',head+Vector((0,0,5)),48),('shoulder',head+Vector((0,0,-21)),78)]:
        for view,direction in [('front',(0,-1,0)),('side',(1,0,0)),('back',(0,1,0)),('oblique',(.62,-.78,0))]:
            cam.location=target+Vector(direction)*500;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();data.ortho_scale=scale
            path=folder/(region+'_'+view+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True);images.append(path.relative_to(out).as_posix())
    names=['pelvis','spine_01','spine_03','spine_05','neck_01','neck_02','head','clavicle_l','upperarm_l','lowerarm_l','hand_l','thigh_l','calf_l','foot_l','ball_l']
    bones={b.name:list(body_arm.matrix_world@b.head_local) for b in body_arm.data.bones if b.name in names}
    report={'character':character,'role':'female_anatomy_reference_only','units':'cm','input_files':[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files.values()],
        'body_bones':len(body_arm.data.bones),'head_bones':len(head_arm.data.bones),'head_to_body_alignment':alignment,'bounds':{'min':minimum.tolist(),'max':maximum.tolist()},'landmarks':bones,'images':images}
    (folder/'reference_report.json').write_text(json.dumps(report,indent=2));bpy.ops.wm.save_as_mainfile(filepath=str(folder/(character+'_Reference.blend')));reports.append(report)
(out/'female_reference_manifest.json').write_text(json.dumps(reports,indent=2));print('FEMALE_REFERENCE_RENDERS_READY',len(reports),sum(len(r['images']) for r in reports),flush=True)
