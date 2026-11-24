"""Prepare centimeter FBX inputs using unreoriented native UEFormat skeletons.

Retains the preview assets separately. Includes 10 reserved material sections
inside the adult head, so game index-based material changes cannot hit Delta.
"""
import json
import sys
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools/blender_libs'),str(ROOT/'vendor/UEFormat/plugins/blender')]
from io_scene_ueformat.importer.import_context import UEFormatImport
from io_scene_ueformat.options import UEModelOptions

OUT=ROOT/'build/model_inputs'
if '--output' in sys.argv:OUT=Path(sys.argv[sys.argv.index('--output')+1]).resolve()
assert OUT.is_relative_to(ROOT)
OUT.mkdir(parents=True,exist_ok=True)
all_reports={}
for variant in ['adult']:
    folder='prototype' if variant=='adult' else 'young_prototype'
    candidate=ROOT/'output/live2d_delta'/folder
    if '--candidate' in sys.argv:candidate=Path(sys.argv[sys.argv.index('--candidate')+1]).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(candidate/'Delta_live2d.blend'))
    mesh=next(o for o in bpy.data.objects if o.type=='MESH')
    old_arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
    old_heads={b.name:old_arm.matrix_world@b.head_local for b in old_arm.data.bones}
    world_positions=[mesh.matrix_world@v.co for v in mesh.data.vertices]
    stem='Hero_Hun/SkinParts/Hun_Body_Simple' if variant=='adult' else 'Young_Hun/SkinParts/Hun_Young_Body'
    native_path=ROOT/'artifacts/extracted/original/HuaShira/Characters/Hero'/f'{stem}.uemodel'
    before=set(bpy.data.objects)
    UEFormatImport(UEModelOptions(scale_factor=1.,reorient_bones=False,
        import_sockets=False,import_morph_targets=False)).import_file(native_path)
    new_objects=set(bpy.data.objects)-before
    arm=next(o for o in new_objects if o.type=='ARMATURE')
    for obj in new_objects:
        if obj.type=='MESH':bpy.data.objects.remove(obj,do_unlink=True)
    errors={b.name:float(((arm.matrix_world@b.head_local)/100-old_heads[b.name]).length)
            for b in arm.data.bones if b.name in old_heads}
    assert len(errors)==(264 if variant=='adult' else 1207)
    (OUT/f'{variant}_native_position_comparison.json').write_text(json.dumps(dict(sorted(errors.items(),key=lambda item:item[1],reverse=True)),indent=2))
    # UEFormat omits the young model's small non-unit finger scales. glTF
    # retained their component positions. Restore these positions while keeping
    # UEFormat's unreoriented bone axes; exact local scales will be restored in UE.
    initial_error=max(errors.values())
    if initial_error>=1e-4:
        assert initial_error<.002,'Unexpected discrepancy beyond the observed small scale differences'
        bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);bpy.context.view_layer.objects.active=arm
        bpy.ops.object.mode_set(mode='EDIT')
        inverse=arm.matrix_world.inverted()
        for bone in arm.data.edit_bones:
            target=inverse@(old_heads[bone.name]*100)
            delta=target-bone.head
            bone.head+=delta;bone.tail+=delta
        bpy.ops.object.mode_set(mode='OBJECT')
        errors={b.name:float(((arm.matrix_world@b.head_local)/100-old_heads[b.name]).length) for b in arm.data.bones}
    assert max(errors.values())<1e-4,('Native/prototype position mismatch',variant,max(errors.values()))
    mesh.parent=None;mesh.matrix_world=Matrix.Identity(4)
    for v,position in zip(mesh.data.vertices,world_positions):v.co=position*100
    mesh.parent=arm
    for modifier in mesh.modifiers:
        if modifier.type=='ARMATURE':modifier.object=arm
    bpy.data.objects.remove(old_arm,do_unlink=True)
    arm.name='Armature';arm.data.name='DeltaNative_'+variant

    materials=list(mesh.data.materials)
    polygon_materials=[p.material_index for p in mesh.data.polygons]
    descriptions={m.name:{'color':list(m.diffuse_color[:]),'front_texture':m.name=='Delta_Live2D_Front'} for m in materials}
    reserved_count=10
    mesh.data.materials.clear()
    for i in range(reserved_count):
        mat=bpy.data.materials.new(f'Delta_Reserved_{i:02}')
        mat.diffuse_color=(0,0,0,1);mesh.data.materials.append(mat)
    for mat in materials:mesh.data.materials.append(mat)
    # Clearing a Blender material list resets every polygon index to zero.
    # Restore the saved assignments after inserting the runtime-reserved slots.
    for polygon,index in zip(mesh.data.polygons,polygon_materials):polygon.material_index=index+reserved_count
    head_verts=[v.co.copy() for v in mesh.data.vertices if v.co.z>(160 if variant=='adult' else 130)]
    center=Vector(np.mean(np.array(head_verts),axis=0))
    head_group=mesh.vertex_groups.get('head') or mesh.vertex_groups.new(name='head')
    bm=bmesh.new();bm.from_mesh(mesh.data)
    deform=bm.verts.layers.deform.verify()
    for i in range(reserved_count):
        tri=[bm.verts.new(center+Vector(p)+Vector((0,i*.001,0))) for p in [(0,0,0),(.1,0,0),(0,.1,0)]]
        for v in tri:v[deform][head_group.index]=1.
        face=bm.faces.new(tri);face.material_index=i
    bm.to_mesh(mesh.data);bm.free();mesh.data.update()
    # BMesh insertion can discard custom corner normals; restore the face's
    # smooth lighting field after adding the reserved material triangles.
    sys.path.insert(0,str(ROOT/'scripts'))
    from delta_surface_normals import soften_face_normals
    soften_face_normals(mesh)

    # Portable texture for the editor importer, independent of FBX material parsing.
    texture_path=ROOT/'artifacts/live2d/Delta_projection_padded.png'
    for mat in materials:
        if mat.name=='Delta_Live2D_Front':
            mat.node_tree.links.new(mat.node_tree.nodes['Principled BSDF'].outputs[0],
                                    mat.node_tree.nodes['Material Output'].inputs['Surface'])
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.01
    bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);mesh.select_set(True)
    bpy.context.view_layer.objects.active=arm
    fbx=OUT/f'Delta_{variant}.fbx'
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,add_leaf_bones=False,bake_anim=False,
        use_mesh_modifiers=False,mesh_smooth_type='FACE',use_tspace=False,object_types={'ARMATURE','MESH'},
        armature_nodetype='NULL',use_armature_deform_only=False,path_mode='COPY',embed_textures=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/f'Delta_{variant}.blend'))

    # Wrong-class placeholders under cloth/groom paths follow the published PBZ cases.
    data=bpy.data.meshes.new('DeltaEmptyMesh')
    data.from_pydata([center,center+Vector((.1,0,0)),center+Vector((0,.1,0))],[],[(0,1,2)])
    empty=bpy.data.objects.new('DeltaEmpty',data);scene.collection.objects.link(empty)
    empty.vertex_groups.new(name='head').add([0,1,2],1.,'REPLACE')
    empty.parent=arm;modifier=empty.modifiers.new('Game skeleton','ARMATURE');modifier.object=arm
    bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);empty.select_set(True)
    bpy.context.view_layer.objects.active=arm
    bpy.ops.export_scene.fbx(filepath=str(OUT/f'Empty_{variant}.fbx'),use_selection=True,
        add_leaf_bones=False,bake_anim=False,use_mesh_modifiers=False,object_types={'ARMATURE','MESH'},
        armature_nodetype='NULL',use_armature_deform_only=False)
    ref=[{'name':b.name,'parent':b.parent.name if b.parent else None,
           'component_position_cm':list(arm.matrix_world@b.head_local)} for b in arm.data.bones]
    all_reports[variant]={'source':'Delta.zip','native_skeleton_source':str(native_path.relative_to(ROOT)),
        'candidate_directory':str(candidate.relative_to(ROOT)),
        'bones':len(arm.data.bones),'native_vs_preview_head_position_error_m':max(errors.values()),
        'initial_native_export_scale_discrepancy_m':initial_error,
        'centimeter_units':True,'reserved_material_sections':reserved_count,
        'materials':descriptions,'material_slots':[m.name for m in mesh.data.materials],
        'front_texture':str(texture_path),'reference':ref,'fbx':str(fbx),
        'warning':'Editor import and cooked transform comparison still required'}
(OUT/'inputs.json').write_text(json.dumps(all_reports,indent=2),encoding='utf-8')
print('GAME_INPUTS_READY',json.dumps({k:{n:v[n] for n in ['bones','native_vs_preview_head_position_error_m']} for k,v in all_reports.items()}))
