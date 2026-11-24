"""Preserve physical machine casing separately from its holographic layers."""
import json
from PIL import Image
from baiqi_source_raster import SourceRaster,ROOT
r=SourceRaster();out=ROOT/'artifacts/baiqi_component_audit/optional_layers';out.mkdir(exist_ok=True);r.set_state(r.source['derived_variants'][0]);records=[]
for layer,parts in [('machine_core',{'Part2'}),('machine_wings',{'Part3'}),('machine_rings',{'Part4'}),('machine_screen',{'Part'})]:
    path=out/(layer+'.png');image=Image.fromarray(r.render(parts));image.save(path);records.append({'layer':layer,'source_parts':sorted(parts),'source_state':'Machine_And_Screen','path':path.relative_to(ROOT).as_posix(),'bbox':image.getbbox()})
for index,name in enumerate(['S1','S2','S3','S4','ArtMesh53'],1):
    r.set_state()
    for d in r.drawables:
        if d['id']==name:d['opacity']=1
    path=out/(name+'.png');image=Image.fromarray(r.render(set(),include_drawables={name}));image.save(path);records.append({'layer':name,'source_parts':['Part40'],'source_drawables':[name],'source_state':'diagnostic single-drawable reveal','path':path.relative_to(ROOT).as_posix(),'bbox':image.getbbox()})
r.set_state();path=out/'shirt_collar.png';Image.fromarray(r.render({'Collar'})).save(path);records.append({'layer':'shirt_collar','source_parts':['Collar'],'source_state':'default','path':path.relative_to(ROOT).as_posix()})
(out/'manifest.json').write_text(json.dumps(records,indent=2));r.close();print('BAIQI_OPTIONAL_LAYERS',len(records),flush=True)
