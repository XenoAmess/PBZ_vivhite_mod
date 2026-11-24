"""UE 5.7 editor commandlet: import the adult-only Delta replacement candidate.

Game-owned skeleton, physics and postprocess placeholders must never be shipped.
The generated allowlist is the sole source of replacement package names.
"""
import json
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'build/model_inputs'
REPORTS=ROOT/'build/reports';REPORTS.mkdir(parents=True,exist_ok=True)
DATA=json.loads((INPUT/'inputs.json').read_text())['adult']
HUN='/HuaShira/Characters/Hero/Hero_Hun'
MOD='/HuaShira/Mods/DeltaLive2D'
SKEL=HUN+'/Hun_Skin_Skeleton'
EAL=unreal.EditorAssetLibrary
TOOLS=unreal.AssetToolsHelpers.get_asset_tools()
LIB=unreal.PBZModToolsLibrary
MEL=unreal.MaterialEditingLibrary
unreal.AssetRegistryHelpers.get_asset_registry().search_all_assets(True)
real=[]
def log(*items):unreal.log('[DELTA] '+' '.join(str(i) for i in items))
def setting(obj,key,value):
    obj.set_editor_property(key,value)
def imported_mesh(filename,path,skeleton=None):
    folder,name=path.rsplit('/',1)
    if EAL.does_asset_exist(path):EAL.delete_asset(path)
    options=unreal.FbxImportUI()
    for k,v in [('import_mesh',True),('import_as_skeletal',True),('import_materials',False),
                ('import_textures',False),('import_animations',False),('create_physics_asset',False),
                ('automated_import_should_detect_type',False),('mesh_type_to_import',unreal.FBXImportType.FBXIT_SKELETAL_MESH)]:setting(options,k,v)
    if skeleton:setting(options,'skeleton',skeleton)
    info=options.get_editor_property('skeletal_mesh_import_data')
    for k,v in [('import_morph_targets',False),('normal_import_method',unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS),
                ('use_t0_as_ref_pose',False),('preserve_smoothing_groups',True),('convert_scene',True),
                ('force_front_x_axis',False),('convert_scene_unit',False),('import_uniform_scale',1.),
                ('update_skeleton_reference_pose',False),('import_meshes_in_bone_hierarchy',True)]:setting(info,k,v)
    task=unreal.AssetImportTask()
    task.filename=str(INPUT/filename);task.destination_path=folder;task.destination_name=name
    task.replace_existing=True;task.automated=True;task.save=False;task.options=options
    task.factory=unreal.FbxFactory()
    TOOLS.import_asset_tasks([task])
    mesh=unreal.load_asset(path)
    assert isinstance(mesh,unreal.SkeletalMesh),'Mesh import failed: '+path
    log('imported',path)
    real.append(path)
    return mesh

body_path=HUN+'/SkinParts/Hun_Body_Simple'
skel=unreal.load_asset(SKEL) if EAL.does_asset_exist(SKEL) else None
body=imported_mesh('Delta_adult.fbx',body_path,skel)
build_settings=unreal.SkeletalMeshEditorSubsystem.get_lod_build_settings(body,0)
build_settings.set_editor_property('use_high_precision_skin_weights',True)
unreal.SkeletalMeshEditorSubsystem.set_lod_build_settings(body,0,build_settings)
if skel is None:
    generated=body_path+'_Skeleton'
    assert EAL.does_asset_exist(generated),'Expected imported placeholder skeleton'
    assert EAL.rename_asset(generated,SKEL)
    skel=unreal.load_asset(SKEL)
assert skel
native_path=next((ROOT/'artifacts/extracted').rglob('Hun_Body_Simple.Hun_Body_Simple.skel.json'))
native=json.loads(native_path.read_text())
imported_pose=json.loads(LIB.dump_ref_skeleton(body))
restored=LIB.apply_reference_pose(body,json.dumps(native))
assert restored.startswith('ok'),restored
log(restored)
pose=json.loads(LIB.dump_ref_skeleton(body))
assert len(pose)==264
native_by_name={b['name']:b for b in native['bones']}
for bone in pose:
    original=native_by_name[bone['name']]
    assert max(abs(x-y) for x,y in zip(bone['t'],original['t']))<.0002,('reference translation',bone['name'])
    dot=sum(x*y for x,y in zip(bone['q'],original['q']))
    assert abs(abs(dot)-1)<.00001,('reference rotation',bone['name'])
    assert max(abs(x-y) for x,y in zip(bone['s'],original['s']))<.0002,('reference scale',bone['name'])

texture_path=MOD+'/Textures/T_DeltaProjection'
task=unreal.AssetImportTask();task.filename=DATA['front_texture']
task.destination_path=MOD+'/Textures';task.destination_name='T_DeltaProjection'
task.replace_existing=True;task.automated=True;task.save=False;task.factory=unreal.TextureFactory()
TOOLS.import_asset_tasks([task])
texture=unreal.load_asset(texture_path);assert texture
texture.set_editor_property('srgb',True)
texture.set_editor_property('virtual_texture_streaming',False)
texture.set_editor_property('mip_gen_settings',unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
EAL.save_loaded_asset(texture)

def material(name,color=None,textured=False):
    path=MOD+'/Materials/'+name
    if EAL.does_asset_exist(path):EAL.delete_asset(path)
    mat=TOOLS.create_asset(name,MOD+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    mat.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property('two_sided',True)
    mat.set_editor_property('used_with_skeletal_mesh',True)
    if textured:
        expression=MEL.create_material_expression(mat,unreal.MaterialExpressionTextureSample,-250,0)
        expression.set_editor_property('texture',texture)
        expression.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
        output='RGB'
    else:
        expression=MEL.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-250,0)
        expression.set_editor_property('constant',unreal.LinearColor(*(color or [0,0,0])[:3],1.))
        output=''
    assert MEL.connect_material_property(expression,output,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(mat);EAL.save_loaded_asset(mat)
    return mat

hidden=material('M_DeltaReserved',[0,0,0])
mats={name:material('M_'+name,color=spec['color'],textured=spec['front_texture']) for name,spec in DATA['materials'].items()}
assigned=[]
for slot in body.get_editor_property('materials'):
    name=str(slot.get_editor_property('material_slot_name'))
    slot.set_editor_property('material_interface',hidden if name.startswith('Delta_Reserved_') else mats[name])
    assigned.append(slot)
assert len(assigned)==18,('Unexpected material slot count',len(assigned),[str(s.get_editor_property('material_slot_name')) for s in assigned])
assert all(str(s.get_editor_property('material_slot_name')).startswith('Delta_Reserved_') for s in assigned[:10])
body.set_editor_property('materials',assigned)

def dummy_physics(name):
    asset=LIB.create_physics_asset(HUN,name,None);EAL.save_loaded_asset(asset);return asset
pa=dummy_physics('PA_Hun');hero_pa=dummy_physics('Hero_Hun_PhysicsAsset')
abp_path=HUN+'/Rig/ABP_Hun_PostProcess'
if not EAL.does_asset_exist(abp_path):
    factory=unreal.AnimBlueprintFactory();factory.set_editor_property('target_skeleton',skel)
    factory.set_editor_property('parent_class',unreal.AnimInstance)
    TOOLS.create_asset('ABP_Hun_PostProcess',HUN+'/Rig',unreal.AnimBlueprint,factory)
post=EAL.load_blueprint_class(abp_path);assert post
LIB.set_mesh_physics_asset(body,pa);LIB.set_post_process_anim_blueprint(body,post)
EAL.save_loaded_asset(body)

empty_path=HUN+'/SkinParts/Hun_Cloth'
empty=imported_mesh('Empty_adult.fbx',empty_path,skel)
LIB.set_mesh_physics_asset(empty,None);LIB.set_post_process_anim_blueprint(empty,None)
slots=list(empty.get_editor_property('materials'))
for slot in slots:slot.set_editor_property('material_interface',hidden)
empty.set_editor_property('materials',slots);EAL.save_loaded_asset(empty)
def duplicate(source,destination):
    if EAL.does_asset_exist(destination):EAL.delete_asset(destination)
    result=EAL.duplicate_asset(source,destination);assert result,destination
    EAL.save_loaded_asset(result);real.append(destination);return result

climax_path='/HuaShira/Characters/Hero/Hero_Hun_Climax/SkinParts/Hun_Body_Climax'
climax=duplicate(body_path,climax_path);LIB.set_mesh_physics_asset(climax,hero_pa);EAL.save_loaded_asset(climax)
for name in ['Hun_Head_New','Hun_Scarf','Hun_Scarf_Climax','Hun_Hair_Band','Hun_BrowLashCard']:
    duplicate(empty_path,HUN+'/SkinParts/'+name)
for name in ['CA_Hun_UpperCloth','CA_Hun_Skirt','CA_Hun_Cape','CA_Hun_Hair01',
             'CA_Hun_UpperCloth_Climax','CA_Hun_Skirt_Climax','CA_Hun_Cape_Climax']:
    duplicate(empty_path,HUN+'/SkinParts/Cloth/'+name)
for name in ['Hun_Hat_00','Hun_Hat_01']:duplicate(empty_path,HUN+'/Hats/'+name)
for name in ['Hun_Brow_V01','Hun_Lash_V01','Normal_Hair_Bangs','Normal_Hair_End','Normal_Hair_Main_Top',
             'Normal_Hair_Ponytail','Normal_Hair_Sideburn','Normal_Hair_Top_Hairline']:
    duplicate(empty_path,'/Game/PBZContent/Characters/Hero/Hun_New_V1/Mesh/'+name)

EAL.save_directory('/HuaShira',only_if_is_dirty=True,recursive=True)
EAL.save_directory('/Game',only_if_is_dirty=True,recursive=True)
assert not any('Young_Hun' in p or 'Hun_Young' in p for p in real)
report={'status':'editor_imported_adult_only','adult_bones':len(pose),'reference_pose':pose,
        'fbx_import_reference_pose':imported_pose,
        'skin_weight_precision_bits':16,
        'source_game_build':'26367565','material_slots':[str(s.get_editor_property('material_slot_name')) for s in assigned],
        'replacement_packages':real,'own_assets_directory':MOD,
        'excluded_placeholders':[SKEL,HUN+'/PA_Hun',HUN+'/Hero_Hun_PhysicsAsset',abp_path],
        'limitations':['No facial morph animation or new cloth physics','Other unlockable outfit bodies are outside this initial candidate',
                      'No runtime claim until tested in game']}
(REPORTS/'editor_import.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
log('DELTA_IMPORT_OK',len(real),'replacement packages; adult only')
