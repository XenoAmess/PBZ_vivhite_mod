"""Read original BaiQi component hierarchy, UVs and variants via Cubism Core.

Uses the official SDK DLL locally. Only user model data and our own metadata
are written to the public reproduction tree; no SDK binaries are copied.
"""
import ctypes as C,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'source/Delta';OUT=ROOT/'repro/baiqi_source';OUT.mkdir(parents=True,exist_ok=True)
LEDGER=ROOT/'characters/baiqi';LEDGER.mkdir(parents=True,exist_ok=True)
dll=ROOT/'tools/cubism_core/Live2DCubismCore.dll';core=C.CDLL(str(dll));VP=C.c_void_p;F=C.c_float;I=C.c_int;U=C.c_uint
class V2(C.Structure):_fields_=[('x',F),('y',F)]
class V4(C.Structure):_fields_=[('x',F),('y',F),('z',F),('w',F)]
def api(name,result,*args):
    f=getattr(core,name);f.restype=result;f.argtypes=list(args);return f
data=(SRC/'Delta.moc3').read_bytes();moc_storage=C.create_string_buffer(len(data)+64);moc_address=(C.addressof(moc_storage)+63)&~63;C.memmove(moc_address,data,len(data))
moc=api('csmReviveMocInPlace',VP,VP,U)(moc_address,len(data));assert moc
size=api('csmGetSizeofModel',U,VP)(moc);model_storage=C.create_string_buffer(size+16);model_address=(C.addressof(model_storage)+15)&~15
model=api('csmInitializeModelInPlace',VP,VP,VP,U)(moc,model_address,size);assert model
update=api('csmUpdateModel',None,VP);update(model)
def count(name):return api('csmGet'+name+'Count',I,VP)(model)
def array(name,kind):return api('csmGet'+name,C.POINTER(kind),VP)(model)
parts=count('Part');drawables=count('Drawable');parameters=count('Parameter')
part_ids=array('PartIds',C.c_char_p);parents=array('PartParentPartIndices',I);part_alpha=array('PartOpacities',F)
draw_ids=array('DrawableIds',C.c_char_p);draw_parent=array('DrawableParentPartIndices',I);texture=array('DrawableTextureIndices',I);orders=array('DrawableDrawOrders',I);alpha=array('DrawableOpacities',F)
render_orders=array('RenderOrders',I)
vertex_counts=array('DrawableVertexCounts',I);positions=array('DrawableVertexPositions',C.POINTER(V2));uvs=array('DrawableVertexUvs',C.POINTER(V2));index_counts=array('DrawableIndexCounts',I);indices=array('DrawableIndices',C.POINTER(C.c_ushort))
mask_counts=array('DrawableMaskCounts',I);masks=array('DrawableMasks',C.POINTER(I));flags=array('DrawableConstantFlags',C.c_ubyte)
blend_modes=array('DrawableBlendModes',I);multiply=array('DrawableMultiplyColors',V4);screen=array('DrawableScreenColors',V4)
param_ids=array('ParameterIds',C.c_char_p);values=array('ParameterValues',F);defaults=array('ParameterDefaultValues',F);minimum=array('ParameterMinimumValues',F);maximum=array('ParameterMaximumValues',F)
part_names=[part_ids[i].decode() for i in range(parts)];draw_names=[draw_ids[i].decode() for i in range(drawables)]
display=json.loads((SRC/'Delta.cdi3.json').read_text(encoding='utf-8'));labels={p['Id']:p['Name'] for p in display['Parts']}
records=[]
for i in range(drawables):
    records.append({'id':draw_names[i],'part':part_names[draw_parent[i]] if draw_parent[i]>=0 else None,'texture':int(texture[i]),'draw_order':int(orders[i]),'render_order':int(render_orders[i]),'opacity':float(alpha[i]),'constant_flags':int(flags[i]),'blend_mode':int(blend_modes[i]),
        'multiply_color':[float(getattr(multiply[i],k)) for k in ['x','y','z','w']], 'screen_color':[float(getattr(screen[i],k)) for k in ['x','y','z','w']],
        'positions_xy':[[float(positions[i][j].x),float(positions[i][j].y)] for j in range(vertex_counts[i])],
        'uvs':[[float(uvs[i][j].x),float(uvs[i][j].y)] for j in range(vertex_counts[i])],
        'indices':[int(indices[i][j]) for j in range(index_counts[i])],'masks':[draw_names[masks[i][j]] for j in range(mask_counts[i])]})
runtime=json.loads((ROOT/'artifacts/live2d/runtime_geometry.json').read_text(encoding='utf-8'));assert runtime['parts']==part_names and [d['id'] for d in runtime['drawables']]==draw_names
part_records=[{'id':part_names[i],'source_name':labels.get(part_names[i],part_names[i]),'parent':part_names[parents[i]] if parents[i]>=0 else None,'opacity':float(part_alpha[i]),
    'children':[part_names[j] for j in range(parts) if parents[j]==i],'drawables':[r['id'] for r in records if r['part']==part_names[i]]} for i in range(parts)]
params=[{'id':param_ids[i].decode(),'default':float(defaults[i]),'min':float(minimum[i]),'max':float(maximum[i])} for i in range(parameters)]
variant_records=[];lookup={p['id']:i for i,p in enumerate(params)}
for path in sorted((SRC/'Emotion').glob('*.exp3.json')):
    expression=json.loads(path.read_text(encoding='utf-8'))
    for i in range(parameters):values[i]=defaults[i]
    for p in expression.get('Parameters',[]):
        i=lookup[p['Id']];value=p['Value'];blend=p.get('Blend','Add')
        target=values[i]+value if blend=='Add' else values[i]*value if blend=='Multiply' else value
        values[i]=max(minimum[i],min(maximum[i],target))
    update(model)
    overrides=[]
    for i,original in enumerate(records):
        current={'positions_xy':[[float(positions[i][j].x),float(positions[i][j].y)] for j in range(vertex_counts[i])],
            'opacity':float(alpha[i]),'draw_order':int(orders[i]),'render_order':int(render_orders[i]),'multiply_color':[float(getattr(multiply[i],k)) for k in ['x','y','z','w']],
            'screen_color':[float(getattr(screen[i],k)) for k in ['x','y','z','w']]}
        delta={k:v for k,v in current.items() if v!=original[k]}
        if delta:overrides.append(dict(delta,id=draw_names[i]))
    variant_records.append({'id':path.stem,'source':path.relative_to(SRC).as_posix(),'parameters':expression.get('Parameters',[]),
        'visible_drawables':[draw_names[i] for i in range(drawables) if alpha[i]>.001],'draw_overrides':overrides})
model_file=json.loads((SRC/'delta.model3.json').read_text(encoding='utf-8'));textures=[{'path':'source/Delta/'+name,'sha256':hashlib.sha256((SRC/name).read_bytes()).hexdigest()} for name in model_file['FileReferences']['Textures']]
geometry={'character':'白绮','source_archive':'resources/Delta.zip','source_moc_sha256':hashlib.sha256(data).hexdigest(),'parts':part_records,'drawables':records,'parameters':params,'variants':variant_records,'textures':textures,
    'note':'Original 2D meshes and atlas UVs. Extraction does not imply 3D migration or completed mod.'}
(OUT/'core_geometry.json').write_text(json.dumps(geometry,ensure_ascii=False,indent=2),encoding='utf-8')
ledger={'character':'白绮','base':'open-licensed female foundation; pending final anatomy validation','source_archive':'resources/Delta.zip','source_counts':{'parts':parts,'drawables':drawables,'parameters':parameters,'expression_presets':len(variant_records)},
    'components':[dict(p,migration_status='not_started',target_objects=[],verification_images=[],notes=[]) for p in part_records],
    'variants':[dict({k:v for k,v in item.items() if k!='draw_overrides'},migration_status='not_started') for item in variant_records],'status':'inventory_only_not_migrated','all_components_accepted':False}
path=LEDGER/'components.json'
if path.exists():
    previous=json.loads(path.read_text(encoding='utf-8'));assert [p['id'] for p in previous['components']]==part_names,'Source inventory changed'
else:path.write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
ledger=json.loads(path.read_text(encoding='utf-8'))
ledger.setdefault('unparented_drawables',[dict(id=d['id'],migration_status='not_started',target_objects=[],verification_images=[]) for d in records if d['part'] is None])
path.write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
print('BAIQI_SOURCE_COMPONENTS_EXTRACTED',parts,drawables,parameters,len(variant_records),flush=True)
