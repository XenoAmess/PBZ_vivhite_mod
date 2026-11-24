"""Verify container membership and cooked adult skeleton against local originals."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'output/live2d_delta/game_candidate'
OUT=ROOT/'artifacts/extracted/candidate_readback';OUT.mkdir(parents=True,exist_ok=True)
ENV=os.environ.copy();ENV['PBZX_AES']=(ROOT/'tools/_private/aes.txt').read_text().strip()
EXPORTER=ROOT/'tools/PbzExport/PbzExport.exe'
GAME=Path(r'Z:\SteamLibrary\steamapps\common\PBZ\ProjectPBZ\Content\Paks')
def export(paks,command,args,extra=None):
    env=ENV.copy()
    if extra:env['PBZX_EXTRA']=str(extra)
    else:env.pop('PBZX_EXTRA',None)
    result=subprocess.run([str(EXPORTER),str(paks),str(ROOT/'tools/Mappings.usmap'),
                           str(ROOT/'tools/oo2core_9_win64.dll'),str(OUT),command,*args],
                          env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (OUT/('export_'+command+'.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
    assert result.returncode==0 and 'FAIL ' not in result.stdout,(command,result.returncode)
    return result.stdout
files=[line.strip().replace('\\','/') for line in export(PACKAGE,'list',['.']).splitlines() if '.uasset' in line.lower()]
assert files,'Candidate container has no packages'
assert not any('young_hun' in p.lower() or 'hun_young' in p.lower() for p in files)
allow=json.loads((ROOT/'build/reports/editor_import.json').read_text())
def path(asset):
    if asset.startswith('/HuaShira/'):return 'ProjectPBZ/Plugins/HuaShira/Content/'+asset[len('/HuaShira/'):]
    assert asset.startswith('/Game/')
    return 'ProjectPBZ/Content/'+asset[len('/Game/'):]
members={p.lower() for p in files}
assert all(path(p).lower()+'.uasset' in members for p in allow['replacement_packages'])
assert all(path(p).lower()+'.uasset' not in members for p in allow['excluded_placeholders'])
permitted={path(p).lower()+'.uasset' for p in allow['replacement_packages']}
assert all(p in permitted or p.startswith('projectpbz/plugins/huashira/content/mods/deltalive2d/') for p in members)
body='ProjectPBZ/Plugins/HuaShira/Content/Characters/Hero/Hero_Hun/SkinParts/Hun_Body_Simple'
climax='ProjectPBZ/Plugins/HuaShira/Content/Characters/Hero/Hero_Hun_Climax/SkinParts/Hun_Body_Climax'
full_body='ProjectPBZ/Plugins/HuaShira/Content/Characters/Hero/Hero_Hun_MoTian/Hun_MoTian_Body_Simple'
skel_output=export(GAME,'skel',[body,climax,full_body],PACKAGE)
assert skel_output.count('skel ')>=3
original=next((ROOT/'artifacts/extracted/ProjectPBZ').rglob('Hun_Body_Simple.Hun_Body_Simple.skel.json'))
reference=json.loads(original.read_text())['bones']
comparisons={}
for package,name in [(body,'Hun_Body_Simple'),(climax,'Hun_Body_Climax'),(full_body,'Hun_MoTian_Body_Simple')]:
    data=json.loads((OUT/(package+'.'+name+'.skel.json')).read_text())
    assert len(data['bones'])==len(reference)==264
    assert 'Hun_Skin_Skeleton' in data['skeleton']
    errors=[]
    for a,b in zip(data['bones'],reference):
        assert (a['name'],a['parent'])==(b['name'],b['parent'])
        assert max(abs(x-y) for x,y in zip(a['t'],b['t']))<.0003
        assert abs(abs(sum(x*y for x,y in zip(a['q'],b['q'])))-1)<.00001
        assert max(abs(x-y) for x,y in zip(a['s'],b['s']))<.0003
        errors.append(max(abs(x-y) for x,y in zip(a['t'],b['t'])))
    names={b['name'] for b in data['bones']}
    assert {'weapon_l_child','weapon_r_child','ik_weapon_l_child','ik_weapon_r_child'}<=names
    assert len(data['materials'])==18
    assert all(m['slot'].startswith('Delta_Reserved_') for m in data['materials'][:10])
    assert all('DeltaLive2D' in str(m['mat']) for m in data['materials'])
    comparisons[name]={'bones':264,'maximum_translation_error_cm':max(errors),
                       'parents_and_rotations_match':True,'material_slots':len(data['materials']),
                       'lods':data['lods']}
mesh_output=export(GAME,'export',['uemodel',body],PACKAGE)
assert 'ok ' in mesh_output and 'Hun_Body_Simple' in mesh_output
assert list(OUT.rglob('Hun_Body_Simple.uemodel'))
material_packages=sorted(p[:-7] for p in files if '/mods/deltalive2d/materials/' in p.lower())
assert len(material_packages)==9,material_packages
export(GAME,'json',material_packages,PACKAGE)
material_checks=[]
for package in material_packages:
    instance=json.loads((OUT/(package+'.json')).read_text())[0]
    assert instance['Type']=='MaterialInstanceConstant'
    assert 'MI_ZeroHun_Cloth_02_b' in instance['Properties']['Parent']['ObjectPath']
    assert instance.get('LoadedMaterialResources')==[],('Unexpected compiled shaders',package)
    remap=instance['CachedData']['ParentLayerIndexRemap']
    assert remap==[0,1],('Native material layers missing',package,remap)
    parameters=instance['Properties']['TextureParameterValues']
    assert {p['ParameterInfo']['Name'] for p in parameters}=={'Albedo','Normal','Mix'}
    assert all(p['ParameterInfo']['Association']=='LayerParameter' and p['ParameterInfo']['Index']==0 for p in parameters)
    material_checks.append({'package':package,'native_parent_layers':remap,'compiled_shaders':0})
texture='ProjectPBZ/Plugins/HuaShira/Content/Mods/DeltaLive2D/Textures/T_DeltaProjection'
export(GAME,'json',[texture],PACKAGE)
texture_metadata=json.loads((OUT/(texture+'.json')).read_text())[0]
assert texture_metadata['Properties'].get('VirtualTextureStreaming') is True,'Projection must cook as VT, not conventional mips'
assert 'VTData' in texture_metadata,'Cooked projection is not a virtual texture'
assert (texture_metadata['VTData']['TileSize'],texture_metadata['VTData']['TileBorderSize'])==(128,2)
print('COOKED_VT_LAYOUT',json.dumps({k:texture_metadata['VTData'][k] for k in ['TileSize','TileBorderSize','Width','Height','LayerTypes']}))
texture_output=export(GAME,'export',['uemodel',texture],PACKAGE)
assert 'ok ' in texture_output and 'T_DeltaProjection' in texture_output
from PIL import Image
image_path=next(OUT.rglob('T_DeltaProjection.png'))
with Image.open(image_path) as decoded:
    texture_size=list(decoded.size)
    assert tuple(decoded.size) in [(1400,2200),(2048,4096)],decoded.size
manifest=json.loads((PACKAGE/'manifest.json').read_text())
for file in manifest['files']:
    assert hashlib.sha256((PACKAGE/file['name']).read_bytes()).hexdigest()==file['sha256']
report={'status':'containers_and_skeleton_verified','runtime_tested':False,'member_count':len(files),
        'container_files':manifest['files'],
        'no_young_assets':True,'no_skeleton_physics_or_abp_placeholders':True,'members':sorted(files),
        'comparison':comparisons,'game_build':'26367565',
        'cooked_texture_size':texture_size,
        'cooked_virtual_texture':{k:texture_metadata['VTData'][k] for k in ['TileSize','TileBorderSize','Width','Height','LayerTypes']},
        'native_materials':material_checks,
        'limits':['Offline verification only; live IK, materials and weapon grip still require the game']}
(PACKAGE/'readback.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
manifest['status']='readback_verified_pending_game';manifest['readback_file']='readback.json'
(PACKAGE/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('DELTA_READBACK_VERIFIED',json.dumps({'members':len(files),'adult_bones':264,'material_slots':18,'texture':texture_size}))
