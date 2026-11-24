"""Require complete, current numeric and visual evidence before runtime QA."""
import argparse,json
from pathlib import Path
from qa.motion_suite import acceptance
parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);parser.add_argument('--review');parser.add_argument('--shape-run');parser.add_argument('--identity-review')
args=parser.parse_args();run=Path(args.run).resolve()
manifest=json.loads((run/'sampling_report.json').read_text(encoding='utf-8'))
review_path=Path(args.review) if args.review else run/'visual_review.json'
if review_path.exists():review=json.loads(review_path.read_text(encoding='utf-8'))
else:
    review={'input_hashes':manifest['input_hashes'],'neutral_shape':'pending',
        'cases':[{'id':id,'status':'pending','notes':[]} for id in manifest['case_ids']],
        'open_defects':['Visual review has not been completed']}
    review_path.write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8')
if args.shape_run:
    shape_dir=Path(args.shape_run).resolve()
    shape_manifest=json.loads((shape_dir/'shape_manifest.json').read_text(encoding='utf-8'))
    shape_review=json.loads((shape_dir/'shape_review.json').read_text(encoding='utf-8'))
    assert shape_review['input_hashes']==shape_manifest['input_hashes'],'Shape review input mismatch'
    review['shape_check']={'coverage_complete':shape_manifest['coverage_complete'],
        'model_sha256':shape_manifest['input_hashes']['model'],'sections':shape_review['sections'],
        'open_defects':shape_review['open_defects']}
if args.identity_review:review['identity_check']=json.loads(Path(args.identity_review).read_text(encoding='utf-8'))
result=acceptance(manifest,review);result['input_hashes']=manifest['input_hashes']
(run/'offline_gate.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
raise SystemExit(0 if result['game_runtime_allowed'] else 2)
