"""Stage an explicit, bounded reproduction set for the public repository.

Copies only the user-authorized models, baked archives, Blender projects and
selected game references. Credentials, private tool state and engine installs
are not part of this manifest.
"""
import hashlib,json,re,shutil,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'repro';DEST.mkdir(exist_ok=True)
items={
 'output/live2d_delta/shoulder_rebuild/Delta_live2d.blend':'models/baseline_001/Delta_live2d.blend',
 'build/shoulder_inputs/Delta_adult.blend':'native_inputs/baseline_001/Delta_adult.blend',
 'output/live2d_delta/hunyuan21_polished/Delta_live2d.blend':'models/rejected_v02/Delta_live2d.blend',
 'output/live2d_delta/qa_repair_001/Delta_live2d.blend':'models/repair_001/Delta_live2d.blend',
 'output/live2d_delta/qa_repair_001/repair_report.json':'models/repair_001/repair_report.json',
 'build/qa_inputs_001/Delta_adult.blend':'native_inputs/repair_001/Delta_adult.blend',
 'build/qa_inputs_001/Delta_adult.fbx':'native_inputs/repair_001/Delta_adult.fbx',
 'build/qa_inputs_001/inputs.json':'native_inputs/repair_001/inputs.json',
 'output/live2d_delta/Delta_Live2D_Adult_v0.2.zip':'baked/rejected_v02/Delta_Live2D_Adult_v0.2.zip',
 'output/live2d_delta/Delta_Live2D_3D_v0.2.zip':'models/rejected_v02/Delta_Live2D_3D_v0.2.zip',
 'output/live2d_delta/qa_runs/baseline_001/Delta_SelfTest.blend':'tests/baseline_001/Delta_SelfTest.blend',
 'output/live2d_delta/qa_runs/baseline_001/sampling_report.json':'tests/baseline_001/sampling_report.json',
 'artifacts/extracted/original/HuaShira/Characters/Hero/Hero_Hun/SkinParts/Hun_Body_Simple.uemodel':'game_reference/Hun_Body_Simple.uemodel',
 'artifacts/live2d/Delta_projection_padded.png':'textures/Delta_front.png',
 'artifacts/live2d/Delta_back_inferred.png':'textures/Delta_back_inferred.png'}
skel=next((ROOT/'artifacts/extracted/ProjectPBZ').rglob('Hun_Body_Simple.Hun_Body_Simple.skel.json'))
items[skel.relative_to(ROOT).as_posix()]='game_reference/adult_reference.skel.json'
for file in (ROOT/'artifacts/extracted/arm_audit').rglob('*.ueanim'):
    items[file.relative_to(ROOT).as_posix()]='game_reference/animations/'+file.name
for run in ['repair_001']:
    for name in ['Delta_SelfTest.blend','sampling_report.json']:
        src=f'output/live2d_delta/qa_runs/{run}/{name}'
        if (ROOT/src).is_file():items[src]=f'tests/{run}/{name}'
denied=re.compile(r'(^|/)(_private|credentials?|secrets?)(/|$)|(^|/)(aes\.txt|\.env|id_rsa|id_ed25519)$',re.I)
token=re.compile(rb'gh[op]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----')
records=[]
for source,target in items.items():
    src=(ROOT/source).resolve();dst=(DEST/target).resolve()
    assert src.is_relative_to(ROOT) and dst.is_relative_to(DEST) and not denied.search(source)
    assert src.is_file(),source
    if src.suffix.lower()=='.zip':
        with zipfile.ZipFile(src) as z:
            assert not any(denied.search(n.replace('\\','/')) for n in z.namelist()),'private path in archive'
            for item in z.infolist():
                if item.file_size<5_000_000 and Path(item.filename).suffix.lower() in ['.py','.json','.txt','.ini','.md']:
                    assert not token.search(z.read(item)),'credential signature in archive'
    elif src.suffix.lower() in ['.py','.json','.txt','.ini','.md']:
        assert not token.search(src.read_bytes()),'credential signature in text'
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    if src.suffix.lower() in ['.py','.json','.txt','.ini','.md']:
        dst.write_bytes(dst.read_bytes().replace(b'\r\n',b'\n'))
    records.append({'path':dst.relative_to(ROOT).as_posix(),'bytes':dst.stat().st_size,
                    'sha256':hashlib.sha256(dst.read_bytes()).hexdigest()})
for name in ['Delta.zip','full.jpg']:
    path=ROOT/'resources'/name;assert path.is_file()
    records.append({'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,
                    'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(DEST/'manifest.json').write_text(json.dumps({'status':'failed_QA_reproduction_snapshots_not_a_finished_release','files':records},indent=2),encoding='utf-8')
print('PUBLIC_REPRO_SNAPSHOT',len(records),'files',sum(r['bytes'] for r in records),'bytes')
