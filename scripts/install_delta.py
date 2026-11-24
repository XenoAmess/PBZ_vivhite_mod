"""Install/remove only the three hash-verified Delta container files."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from datetime import datetime,timezone

HERE=Path(__file__).resolve().parent
PACKAGE=HERE if (HERE/'manifest.json').is_file() else HERE.parent/'output/live2d_delta/game_candidate'
parser=argparse.ArgumentParser()
parser.add_argument('--game-root',default=r'Z:\SteamLibrary\steamapps\common\PBZ')
parser.add_argument('--uninstall',action='store_true')
args=parser.parse_args()
game=Path(args.game_root).resolve()
paks=(game/'ProjectPBZ/Content/Paks').resolve();assert paks.is_dir()
target=(paks/'~mods').resolve();assert target.is_relative_to(paks)
assert (PACKAGE/'readback.json').is_file(),'Readback verification is required'
assert json.loads((PACKAGE/'cooked_deformation.json').read_text())['status']=='cooked_geometry_and_pose_check','Cooked pose validation is required'
manifest=json.loads((PACKAGE/'manifest.json').read_text())
assert manifest['status'] in ['readback_verified_pending_game','runtime_verified_adult_basic']
assert json.loads((PACKAGE/'readback.json').read_text())['container_files']==manifest['files'],'Readback does not match this package'
assert json.loads((PACKAGE/'cooked_deformation.json').read_text())['container_files']==manifest['files'],'Pose verification does not match this package'
process_script="@(Get-CimInstance Win32_Process | Where-Object { $_.Name -like '*PBZ*' } | Select-Object ProcessId,ExecutablePath) | ConvertTo-Json -Compress"
result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',process_script],
                      capture_output=True,text=True,encoding='utf-8',errors='replace',check=True)
processes=json.loads(result.stdout or '[]')
if isinstance(processes,dict):processes=[processes]
assert not [p for p in processes if p.get('ExecutablePath') and Path(p['ExecutablePath']).resolve().is_relative_to(game)],'Close the game first'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
operations=[]
for info in manifest['files']:
    name=info['name'];assert name in ['z_DeltaLive2D_P.pak','z_DeltaLive2D_P.utoc','z_DeltaLive2D_P.ucas']
    source=PACKAGE/name;destination=(target/name).resolve()
    assert destination.parent==target
    assert source.is_file() and sha(source)==info['sha256'],('Invalid package',name)
    if destination.exists():
        assert sha(destination)==info['sha256'],('Existing file differs; left unchanged',str(destination))
    operations.append((source,destination,info))
if args.uninstall:
    for _,destination,_ in operations:
        if destination.is_file():destination.unlink()
else:
    target.mkdir(exist_ok=True)
    for source,destination,info in operations:
        if not destination.exists():shutil.copy2(source,destination)
        assert sha(destination)==info['sha256']
receipt={'operation':'uninstall' if args.uninstall else 'install','utc':datetime.now(timezone.utc).isoformat(),
         'target':str(target),'files':manifest['files'],'runtime_tested':False}
(PACKAGE/'install_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
manifest['installed']=not args.uninstall
(PACKAGE/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('DELTA_REMOVED' if args.uninstall else 'DELTA_INSTALLED',target)
