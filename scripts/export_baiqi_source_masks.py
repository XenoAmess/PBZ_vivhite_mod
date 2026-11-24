"""Write original clipping masks for 3D material projection."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
from OpenGL import GL
from baiqi_source_raster import SourceRaster,ROOT
r=SourceRaster();out=ROOT/'artifacts/baiqi_component_audit/masks';out.mkdir(exist_ok=True);records=[]
groups=sorted(set(tuple(d['masks']) for d in r.source['drawables'] if d['masks']))
for group in groups:
    r.mask(group);fbo,_=r.mask_cache[group];GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,fbo);GL.glFinish();raw=GL.glReadPixels(0,0,r.width,r.height,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE)
    rgba=np.frombuffer(raw,dtype=np.uint8).reshape(r.height,r.width,4)[::-1].copy();name=hashlib.sha256(','.join(group).encode()).hexdigest()[:16]+'.png';Image.fromarray(rgba).save(out/name);records.append({'mask_drawables':list(group),'path':(out/name).relative_to(ROOT).as_posix()})
(out/'manifest.json').write_text(json.dumps(records,indent=2),encoding='utf-8');r.close();print('BAIQI_ORIGINAL_MASKS',len(records))
