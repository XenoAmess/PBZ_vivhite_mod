"""Preserve the complete static shape audit and its exact execution inputs."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('run');args=p.parse_args();run=(ROOT/args.run).resolve();assert run.is_relative_to(ROOT)
report=json.loads((run/'shape_manifest.json').read_text(encoding='utf-8'));assert report['coverage_complete']
inputs={'model':(ROOT/report['candidate'],'code/inputs/candidate.blend'),'suite':(ROOT/'qa/shape_audit_v1.json','code/qa/shape_audit_v1.json'),'runner':(ROOT/'scripts/render_shape_audit.py','code/scripts/render_shape_audit.py')}
if 'materials' in report['input_hashes']:inputs['materials']=(ROOT/'scripts/qa_materials.py','code/scripts/qa_materials.py')
for kind,(path,_) in inputs.items():assert hashlib.sha256(path.read_bytes()).hexdigest()==report['input_hashes'][kind],kind
out=ROOT/'output/qa_archives';out.mkdir(exist_ok=True);archive=out/(run.name+'_Shape_v'+report['shape_suite_version']+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
    for path in sorted(run.rglob('*')):
        if path.is_file() and path.suffix not in ['.blend1','.log']:z.write(path,path.relative_to(run).as_posix())
    for path,name in inputs.values():z.write(path,name)
    z.writestr('REPRODUCE.txt','Failed whole-body shape baseline. Not a finished model or installable Mod.\nFrom the extracted archive:\nblender --background --python code/scripts/render_shape_audit.py -- --candidate inputs/candidate.blend --output rendered\nThe exact source model, suite, runner and hashes are included.\n')
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
record={'file':archive.name,'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'input_hashes':report['input_hashes'],'status':'failed_whole_body_shape_review'}
archive.with_suffix('.json').write_text(json.dumps(record,indent=2));print('SHAPE_ARCHIVE',json.dumps(record))
