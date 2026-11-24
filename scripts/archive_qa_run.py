"""Archive one complete rendered ROM run for a repository Release."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('run');args=parser.parse_args()
run=(ROOT/args.run).resolve();assert run.is_relative_to(ROOT)
report=json.loads((run/'sampling_report.json').read_text(encoding='utf-8'))
assert report['coverage_complete'],'Do not publish a partial run as a complete render archive'
inputs={
 'model':(ROOT/report['native_input'],'code/inputs/candidate.blend'),
 'suite':(ROOT/'qa/suites/humanoid_v1.json','code/qa/suites/humanoid_v1.json'),
 'runner':(ROOT/'scripts/build_self_test_suite.py','code/scripts/build_self_test_suite.py'),
 'contract':(ROOT/'qa/motion_suite.py','code/qa/motion_suite.py')}
for key,path in {'materials':'scripts/qa_materials.py','identity':'qa/identity.py','character':'characters/baiqi/source_contract.json','rig_preflight':'scripts/qa_rig_preflight.py','rig_contract':'qa/rig_binding.py'}.items():
    if key in report['input_hashes']:inputs[key]=(ROOT/path,'code/'+path)
if 'rig_preflight' in report['input_hashes']:inputs['native_reference']=(ROOT/'repro/native_inputs/repair_015/Delta_adult.blend','code/repro/native_inputs/repair_015/Delta_adult.blend')
for kind,(file,_) in inputs.items():
    expected=report['rig_preflight']['native_reference_sha256'] if kind=='native_reference' else report['input_hashes'][kind]
    assert hashlib.sha256(file.read_bytes()).hexdigest()==expected,('Execution input changed',kind)
out=ROOT/'output/qa_archives';out.mkdir(exist_ok=True)
archive=out/(run.name+'_ROM_v'+report['suite_version']+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
    for file in sorted(run.rglob('*')):
        if file.is_file() and file.suffix.lower() not in ['.blend1','.log']:
            relative=file.relative_to(run).as_posix()
            assert '_private' not in relative and not relative.startswith('.')
            z.write(file,relative)
    for file,name in inputs.values():z.write(file,name)
    z.writestr('REPRODUCE.txt','This is a failed/pending QA snapshot, not a finished Mod.\nThe original runner, exact suite bytes and native input are in code/.\nFrom the extracted archive, run Blender with:\nblender --background --python code/scripts/build_self_test_suite.py -- --candidate inputs/candidate.blend --suite qa/suites/humanoid_v1.json --output rendered\nAll inputs are checked against sampling_report.json SHA256 values before archiving.\n')
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
record={'file':archive.name,'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'input_hashes':report['input_hashes'],'status':report['status']}
archive.with_suffix('.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print('QA_RENDER_ARCHIVE',json.dumps(record),flush=True)
