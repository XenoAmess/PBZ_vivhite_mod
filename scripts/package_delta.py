"""Package only verified adult replacement assets and Delta-owned dependencies.

Does not install the files or run the game. Excludes skeleton/physics/ABP
placeholders and every young character asset by construction and assertion.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--engine',default=r'E:\UE_5.7')
parser.add_argument('--allowlist',type=Path,default=ROOT/'build/reports/editor_import.json')
parser.add_argument('--out',type=Path,default=ROOT/'output/live2d_delta/game_candidate')
parser.add_argument('--container-name',default='z_DeltaLive2D_P')
args=parser.parse_args()
engine=Path(args.engine)
project=ROOT/'build/UE/ProjectPBZ/ProjectPBZ.uproject'
cooked=project.parent/'Saved/Cooked/Windows'
metadata=cooked/'ProjectPBZ/Metadata'
allow=json.loads(args.allowlist.read_text(encoding='utf-8'))
assert allow['adult_bones']==264
paths={}
def add_asset(asset):
    assert 'Young_Hun' not in asset and 'Hun_Young' not in asset,asset
    assert asset not in allow['excluded_placeholders'],asset
    if asset.startswith('/HuaShira/'):
        relative='ProjectPBZ/Plugins/HuaShira/Content/'+asset[len('/HuaShira/'):]
    elif asset.startswith('/Game/'):
        relative='ProjectPBZ/Content/'+asset[len('/Game/'):]
    else:raise AssertionError(asset)
    header=cooked/(relative+'.uasset');assert header.is_file(),'Missing cooked asset: '+asset
    for extension in ['.uasset','.uexp','.ubulk','.uptnl']:
        path=cooked/(relative+extension)
        if path.is_file():paths[path]='../../../'+relative+extension
for asset in allow['replacement_packages']:add_asset(asset)
if 'owned_assets' in allow:
    for asset in allow['owned_assets']:
        add_asset(asset)
else:
    own_directory=cooked/'ProjectPBZ/Plugins/HuaShira/Content/Mods/DeltaLive2D'
    for header in own_directory.rglob('*.uasset'):
        relative=header.relative_to(cooked/'ProjectPBZ/Plugins/HuaShira/Content').with_suffix('').as_posix()
        add_asset('/HuaShira/'+relative)
assert paths
for p in ['packagestore.manifest','scriptobjects.bin']:assert (metadata/p).is_file(),p
out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
name=args.container_name
assert name.isascii() and name.replace('_','').isalnum() and name.endswith('_P'),name
temporary=ROOT/'build/container_metadata'/name;temporary.mkdir(parents=True,exist_ok=True)
response=temporary/'assets_response.txt'
response.write_text('\n'.join(f'"{p}" "{mount}" -compress' for p,mount in sorted(paths.items()))+'\n',encoding='utf-8')
commands=temporary/'commands.txt'
commands.write_text(f'-Output="{out / (name+".utoc")}" -ContainerName={name} -ResponseFile="{response}"\n',encoding='utf-8')
pak=engine/'Engine/Binaries/Win64/UnrealPak.exe'
command=[str(pak),str(project),f'-CreateGlobalContainer={temporary / "global.utoc"}',
         f'-PackageStoreManifest={metadata / "packagestore.manifest"}',f'-CookedDirectory={cooked}',
         f'-Commands={commands}',f'-ScriptObjects={metadata / "scriptobjects.bin"}',
         '-compressionformats=Oodle','-compresslevel=4','-compressmethod=Kraken','-platform=Windows','-unattended']
with (temporary/'container.log').open('wb') as stream:
    result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
assert result.returncode==0,('IoStore build failed',result.returncode)
note=temporary/'DeltaLive2D.txt'
scope = ('Standalone BaiQi adult appearance' if allow.get('outfit_id') else 'Adult Soul replacement assets')
note.write_text(scope + '\n',encoding='utf-8')
companion=temporary/'pak_response.txt'
companion.write_text(f'"{note}" "../../../ProjectPBZ/Content/Mods/DeltaLive2D/DeltaLive2D.txt"\n',encoding='utf-8')
companion_output=temporary/(name+'.pak')
assert companion_output.resolve().parent==temporary.resolve()
if companion_output.exists():companion_output.unlink()
with (temporary/'companion_pak.log').open('wb') as stream:
    result=subprocess.run([str(pak),str(companion_output),f'-create={companion}',
                           '-platform=Windows','-unattended'],stdout=stream,stderr=subprocess.STDOUT)
assert result.returncode==0,('Companion pak failed',result.returncode)
companion_output.replace(out/(name+'.pak'))
files=[]
for extension in ['.pak','.utoc','.ucas']:
    path=out/(name+extension);assert path.is_file() and path.stat().st_size>0
    files.append({'name':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
report={'status':'container_built_pending_readback','scope':scope,
        'steam_build':'26367565','replacement_packages':allow['replacement_packages'],
        'excluded_placeholders':allow['excluded_placeholders'],'files':files,
        'runtime_tested':False,'installed':False}
for key in ('form','source_sha256','source_models','body_sha256','combined_bones','wardrobe',
            'outfit_id','framework_slot','coat_slots','default_coat_visible'):
    if key in allow:
        report[key]=allow[key]
(out/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('DELTA_CONTAINER_BUILT',json.dumps(files))
