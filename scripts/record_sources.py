"""Record reproducible inputs, downloaded mapping and local generated artifacts.

No keys, login data, or game archive contents are included in this manifest.
"""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(4*1024*1024): h.update(b)
    return {'path':str(path.relative_to(ROOT)).replace('\\','/'),
            'bytes':path.stat().st_size,'sha256':h.hexdigest()}
paths=[ROOT/p for p in ['resources/Delta.zip','resources/full.jpg',
       'tools/Mappings.usmap','tools/oo2core_9_win64.dll',
       'artifacts/live2d/Delta_front.png','artifacts/live2d/Delta_projection_padded.png','artifacts/live2d_reconstruction/input.png',
       'artifacts/live2d_reconstruction/Delta_shape.glb',
       'artifacts/live2d_reconstruction_21/Delta_shape.glb','artifacts/live2d_reconstruction_21/shape_report.json']]
paths += list((ROOT/'scripts').glob('*.py'))
paths += [p for p in (ROOT/'output/live2d_delta/prototype').glob('*') if p.suffix!='.blend1']
paths += [p for p in (ROOT/'output/live2d_delta/hunyuan21_polished').glob('*') if p.suffix!='.blend1']
paths += [p for p in (ROOT/'output/live2d_delta/arm_semantic_review').glob('*') if p.is_file()]
paths += [p for p in (ROOT/'output/live2d_delta/game_candidate').glob('*') if p.is_file() and p.suffix!='.zip']
versions={}
for name in ['GameModdingKnowledge','Hunyuan3D-2','Hunyuan3D-2.1','UEFormat','AESDumpster']:
    p=subprocess.run(['git','-C',str(ROOT/'vendor'/name),'rev-parse','HEAD'],capture_output=True,text=True)
    versions[name]=p.stdout.strip()
report={'recorded_at_utc':datetime.now(timezone.utc).isoformat(),
        'active_model':'Delta.zip Live2D version',
        'active_candidate':'output/live2d_delta/hunyuan21_polished',
        'replacement_scope':'adult normal, Climax and Inheritance/MoTian; no young assets',
        'full_jpg':'Separate second model, not used in active reconstruction',
        'game_path':r'Z:\SteamLibrary\steamapps\common\PBZ','steam_build':'26367565',
        'source_commits':versions,'files':[digest(p) for p in paths if p.is_file()],
        'game_runtime_tested':True,'visual_quality':'local basic checks passed; user visual acceptance pending',
        'runtime_review':'output/live2d_delta/game_candidate/runtime_review.json'}
(ROOT/'source-lock.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print('Source lock written:',len(report['files']),'files')
