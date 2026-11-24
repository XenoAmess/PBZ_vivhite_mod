"""Extract only the two user-named female anatomy references for local QA."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parts=[
 'ProjectPBZ/Plugins/HuaShira/Content/Characters/NPC/YuEr/SkinParts/YuEr_Body',
 'ProjectPBZ/Plugins/HuaShira/Content/Characters/NPC/YuEr/SkinParts/YuEr_Head',
 'ProjectPBZ/Plugins/HuaShira/Content/Characters/EliteBoss/MuXiaoKui/SkinParts/MuXiaoKui_Body',
 'ProjectPBZ/Plugins/HuaShira/Content/Characters/EliteBoss/MuXiaoKui/SkinParts/MuXiaoKui_Head']
log=ROOT/'artifacts/female_reference_export.log'
with log.open('wb') as stream:r=subprocess.run([sys.executable,str(ROOT/'scripts/export_game.py'),'female_reference','export','uemodel',*parts],stdout=stream,stderr=subprocess.STDOUT)
print('FEMALE_REFERENCE_EXPORT_EXIT',r.returncode)
if r.returncode:raise SystemExit(r.returncode)
files=sorted((ROOT/'artifacts/extracted/female_reference').rglob('*.uemodel'))
assert len(files)>=4,'Reference export incomplete; inspect local log'
(ROOT/'artifacts/female_reference_export_manifest.json').write_text(json.dumps({'selected_packages':parts,'files':[p.relative_to(ROOT).as_posix() for p in files]},indent=2),encoding='utf-8')
print('FEMALE_REFERENCE_MODELS_READY',[p.name for p in files])
