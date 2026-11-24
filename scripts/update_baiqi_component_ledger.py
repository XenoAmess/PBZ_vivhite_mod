"""Bind every original component to actual objects, without granting acceptance."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--candidate',default='output/live2d_delta/baiqi_component_assembly_006/BaiQi_Assembly.blend');p.add_argument('--output',default='output/live2d_delta/baiqi_component_assembly_007');p.add_argument('--inspect-only',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=ROOT/a.output;out.mkdir(parents=True,exist_ok=True)
source=json.loads((ROOT/'repro/baiqi_source/core_geometry.json').read_text(encoding='utf-8'));ledgerpath=ROOT/'characters/baiqi/components.json';ledger=json.loads(ledgerpath.read_text(encoding='utf-8'));bpy.ops.wm.open_mainfile(filepath=str(ROOT/a.candidate));parts={p['id']:p for p in source['parts']}
def desc(name):
    result={name}
    for child in parts[name]['children']:result.update(desc(child))
    return result
base=bpy.data.objects['BaiQi_FemaleFoundation'];base['baiqi_source_parts']=json.dumps(sorted((desc('Face')-{'Glasses'})|{'Body','Neck','Leg2','Part31','Part35','Part32','Part36','Part33','Part37','Fhair'}));base['baiqi_face_shadow_drawables']=json.dumps([d['id'] for d in source['drawables'] if d['part']=='Fhair' and 'Facecolor' in d['masks']])
objects={p:set() for p in parts}
for obj in [o for o in bpy.data.objects if o.type=='MESH']:
    for part in json.loads(obj.get('baiqi_source_parts','[]')):
        if part in objects:objects[part].add(obj.name)
def targets(part):
    result=objects[part].copy()
    for c in parts[part]['children']:result.update(targets(c))
    return result
for p in ledger['components']:
    p['target_objects']=sorted(targets(p['id']));p['migration_status']='assembled_pending_review' if p['target_objects'] else 'not_started';p['verification_images']=[]
    if p['id'] in ['Part33','Part37']:
        p['migration_status']='native_hand_pose_pending_review';p['notes']=['Represented by the authored female skinned hand. The source alternate gesture must be checked with native finger and wrist actions.']
    if not p['drawables']:p['notes']=['Original hierarchy/container, represented by the union of mapped child components.']
for v in ledger['variants']:v['migration_status']='blender_state_connected_pending_review';v['target_objects']=['BaiQi_Source_State_Controller'];v['verification_images']=[]
ledger['unparented_drawables']=[{'id':d['id'],'role':'original rear coat backing','migration_status':'assembled_pending_review','target_objects':['BaiQi coat side back'],'verification_images':[]} for d in source['drawables'] if d['part'] is None]
ledger['status']='all_source_components_mapped_not_accepted';ledger['all_components_accepted']=False;ledger['accepted_components']=0;ledger['mapped_components']=sum(bool(p['target_objects']) for p in ledger['components']);ledger['source_counts']['unparented_drawables']=len(ledger['unparented_drawables'])
assert ledger['mapped_components']==98
contract={'schema_version':1,'character':'白绮','source_moc_sha256':source['source_moc_sha256'],'components':[{'id':p['id'],'source_name':p['source_name']} for p in source['parts']],'variants':[{'id':v['id']} for v in source['variants']],'unparented_drawables':[{'id':d['id']} for d in source['drawables'] if d['part'] is None]}
contractpath=ROOT/'characters/baiqi/source_contract.json'
if contractpath.exists():assert json.loads(contractpath.read_text(encoding='utf-8'))==contract,'Original source contract changed'
else:contractpath.write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
model=ROOT/a.candidate if a.inspect_only else out/'BaiQi_Assembly.blend'
if not a.inspect_only:bpy.ops.wm.save_as_mainfile(filepath=str(model))
ledger['candidate']=model.relative_to(ROOT).as_posix();ledger['model_sha256']=hashlib.sha256(model.read_bytes()).hexdigest();ledgerpath.write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
review={'character':'白绮','model_sha256':ledger['model_sha256'],'source_contract_sha256':hashlib.sha256(contractpath.read_bytes()).hexdigest(),'status':'pending_visual_review','game_runtime_allowed':False,'components':[{'id':p['id'],'target_objects':p['target_objects'],'status':'pending','verification_images':[]} for p in ledger['components']],'variants':[{'id':v['id'],'target_objects':v['target_objects'],'status':'pending','verification_images':[]} for v in ledger['variants']],'unparented_drawables':[dict(p,status='pending') for p in ledger['unparented_drawables']],'open_defects':['Multi-view garment and head review is incomplete','Source alternate hand gestures not yet validated','Optional holographic controls are not implemented in the game','Full ROM visual review not completed']}
(out/'identity_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8');print('BAIQI_COMPONENTS_MAPPED',ledger['mapped_components'],'accepted',ledger['accepted_components'],flush=True)
