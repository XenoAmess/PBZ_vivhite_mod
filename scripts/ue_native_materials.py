"""Reuse the game's existing shader parent; never ship a compiled master."""
import json
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/reports'
report=json.loads((OUT/'editor_import.json').read_text())
data=json.loads((ROOT/'build/model_inputs/inputs.json').read_text())['adult']
MOD='/HuaShira/Mods/DeltaLive2D'
PARENT='/Game/PBZContent/Characters/Hero/Hun_New_V2b/Material/MI_ZeroHun_Cloth_02_b'
DUMMY='/Game/PBZContent/Mods/M_DeltaDummyMaster'
EAL=unreal.EditorAssetLibrary;MEL=unreal.MaterialEditingLibrary
TOOLS=unreal.AssetToolsHelpers.get_asset_tools();LIB=unreal.PBZModToolsLibrary
unreal.AssetRegistryHelpers.get_asset_registry().search_all_assets(True)
def create(path,cls,factory):
    if EAL.does_asset_exist(path):EAL.delete_asset(path)
    folder,name=path.rsplit('/',1);return TOOLS.create_asset(name,folder,cls,factory)
master=create(DUMMY,unreal.Material,unreal.MaterialFactoryNew())
master.set_editor_property('used_with_skeletal_mesh',True)
EAL.save_loaded_asset(master)
parent=create(PARENT,unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
MEL.set_material_instance_parent(parent,master);EAL.save_loaded_asset(parent)
def texture(name,file,normal=False,linear=False):
    task=unreal.AssetImportTask();task.filename=str(file)
    task.destination_path=MOD+'/Textures';task.destination_name=name
    task.automated=True;task.replace_existing=True;task.save=False;task.factory=unreal.TextureFactory()
    TOOLS.import_asset_tasks([task]);tex=unreal.load_asset(MOD+'/Textures/'+name);assert tex
    tex.set_editor_property('srgb',not (normal or linear))
    tex.set_editor_property('power_of_two_mode',unreal.TexturePowerOfTwoSetting.NONE)
    tex.set_editor_property('mip_gen_settings',unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP)
    tex.set_editor_property('lod_group',unreal.TextureGroup.TEXTUREGROUP_PROJECT02)
    if normal:tex.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP)
    elif linear:tex.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_MASKS)
    tex.set_editor_property('compression_no_alpha',not normal)
    if not (normal or linear):tex.set_editor_property('adjust_brightness',.9)
    tex.set_editor_property('virtual_texture_streaming',True)
    EAL.save_loaded_asset(tex)
    assert tex.get_editor_property('virtual_texture_streaming'),('VT disabled',name)
    unreal.log('[DELTA] VT_INPUT '+name+' '+str(tex.blueprint_get_size_x())+'x'+str(tex.blueprint_get_size_y()))
    return tex
inputs=ROOT/'artifacts/native_material_inputs'
front=texture('T_DeltaProjection',inputs/'ProjectionPOT.png')
rear=texture('T_DeltaBack',inputs/'BackProjectionPOT.png')
normal=texture('T_DeltaFlatNormal',inputs/'FlatNormal.png',normal=True)
arm=texture('T_DeltaMatteARM',inputs/'MatteARM.png',linear=True)
def instance(name,albedo):
    path=MOD+'/Materials/'+name
    mi=create(path,unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi,parent)
    LIB.clear_material_instance_parameters(mi)
    for parameter,value in [('Albedo',albedo),('Normal',normal),('Mix',arm)]:
        LIB.set_material_texture_parameter(mi,parameter,1,0,value)
    for parameter,value in [('NormalIntensity',0.),('BaseColor Intensity',1.)]:
        LIB.set_material_scalar_parameter(mi,parameter,1,0,value)
    for parameter,value in [('Normal Strength',0.),('ClothFuzzIntensity',0.),('ClothIntensity',0.),('Specular',.15)]:
        LIB.set_material_scalar_parameter(mi,parameter,1,0,value)
    LIB.set_material_scalar_parameter(mi,'NormalIntensity',1,1,0.)
    LIB.set_material_scalar_parameter(mi,'Roughness Overlay Intensity',1,1,0.)
    LIB.set_material_scalar_parameter(mi,'FuzzIntensity',2,0,0.)
    for parameter in ['Wetness Min','Wetness Max','RainDrops | StaticDrops Intensity','RainDrops | DrippingDrop Intensity']:
        LIB.set_material_scalar_parameter(mi,parameter,0,-1,0.)
    MEL.update_material_instance(mi);EAL.save_loaded_asset(mi);return mi
materials={}
for name,spec in data['materials'].items():
    albedo=front if spec['front_texture'] else rear
    materials[name]=instance('M_'+name,albedo)
reserved=instance('M_DeltaReserved',texture('T_DeltaReserved',inputs/'DeltaReserved.png'))
base_body='/HuaShira/Characters/Hero/Hero_Hun/SkinParts/Hun_Body_Simple'
unused_full='/HuaShira/Characters/Hero/Hero_Hun/SkinParts/Hun_Body'
report['replacement_packages']=[p for p in report['replacement_packages'] if p!=unused_full]
inheritance='/HuaShira/Characters/Hero/Hero_Hun_MoTian'
inheritance_body=inheritance+'/Hun_MoTian_Body_Simple'
if EAL.does_asset_exist(inheritance_body):EAL.delete_asset(inheritance_body)
full=EAL.duplicate_asset(base_body,inheritance_body);assert full
EAL.save_loaded_asset(full)
if inheritance_body not in report['replacement_packages']:report['replacement_packages'].append(inheritance_body)
hidden_paths=[inheritance+'/Cloth/'+n for n in ['CA_SM_Hun_MoTian_Cloth01','CA_SM_Hun_MoTian_Cloth02',
    'CA_SM_Hun_MoTian_Cloth03','CA_Hun_MoTian_Hair01','Hun_MoTian_Hair_Band']]
hidden_paths+=['/HuaShira/Characters/Hero/Hero_Hun/Hats/Hun_Hat_MoTian',
               '/HuaShira/Characters/Hero/Hero_Hun/SkinParts/Hun_Head']
hidden_paths+=['/Game/PBZContent/Characters/Hero/Hun_MoTian/Mesh/MoTian_Hair_'+n
               for n in ['Bangs','Back','Main','Tail','Side','Detail']]
for path in hidden_paths:
    if EAL.does_asset_exist(path):EAL.delete_asset(path)
    hidden=EAL.duplicate_asset('/HuaShira/Characters/Hero/Hero_Hun/SkinParts/Hun_Cloth',path);assert hidden
    EAL.save_loaded_asset(hidden)
    if path not in report['replacement_packages']:report['replacement_packages'].append(path)
for asset in report['replacement_packages']:
    mesh=unreal.load_asset(asset);assert isinstance(mesh,unreal.SkeletalMesh)
    slots=[]
    for slot in mesh.get_editor_property('materials'):
        name=str(slot.get_editor_property('material_slot_name'))
        slot.set_editor_property('material_interface',materials.get(name,reserved));slots.append(slot)
    mesh.set_editor_property('materials',slots);EAL.save_loaded_asset(mesh)
    if len(slots)==18:
        # The inferred hair/nose volume produced heavy self-shadow on the
        # illustrated face. Keep body-back shadows; exclude front/hair casters.
        for name in ['Delta_Live2D_Front','Delta_Inferred_Hair_Back']:
            assert LIB.set_section_cast_shadow(mesh,name,False)>0,(asset,name)
        EAL.save_loaded_asset(mesh)
report['excluded_placeholders']=sorted(set(report['excluded_placeholders']+[PARENT,DUMMY]))
report['material_strategy']='native_game_parent_layer_0'
report['native_material_parent']=PARENT
report['virtual_textures']=True
(OUT/'editor_import.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('[DELTA] NATIVE_MATERIALS_OK; dummy masters and parents excluded')
