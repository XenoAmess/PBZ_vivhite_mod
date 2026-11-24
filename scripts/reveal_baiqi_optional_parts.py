"""Diagnostic source artwork reveal; this is not an original expression state."""
from PIL import Image
from baiqi_source_raster import SourceRaster,ROOT
r=SourceRaster();out=ROOT/'artifacts/baiqi_component_audit/body_layers'
for part in ['Part40','Part34','Part37','Part33','Part']:
    r.set_state()
    for d in r.drawables:
        if d['part']==part:d['opacity']=1
    im=Image.fromarray(r.render({part}));im.save(out/(part+'_diagnostic.png'))
r.close()
