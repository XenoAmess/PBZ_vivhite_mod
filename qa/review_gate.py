"""Require complete, current numeric and visual evidence before runtime QA."""
import argparse,json
from pathlib import Path
from qa.motion_suite import acceptance
parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);parser.add_argument('--review')
args=parser.parse_args();run=Path(args.run).resolve()
manifest=json.loads((run/'sampling_report.json').read_text(encoding='utf-8'))
review_path=Path(args.review) if args.review else run/'visual_review.json'
if review_path.exists():review=json.loads(review_path.read_text(encoding='utf-8'))
else:
    review={'input_hashes':manifest['input_hashes'],'neutral_shape':'pending',
        'cases':[{'id':id,'status':'pending','notes':[]} for id in manifest['case_ids']],
        'open_defects':['Visual review has not been completed']}
    review_path.write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8')
result=acceptance(manifest,review);result['input_hashes']=manifest['input_hashes']
(run/'offline_gate.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
raise SystemExit(0 if result['game_runtime_allowed'] else 2)
