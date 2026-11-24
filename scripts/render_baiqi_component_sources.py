"""Render original BaiQi parts and appearance variants for migration review."""
import json,os
from pathlib import Path
os.environ['LIVE2D_PY_NO_BANNER']='1'
import glfw,live2d,numpy as np
from PIL import Image
from OpenGL import GL
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'artifacts/baiqi_component_audit';out.mkdir(parents=True,exist_ok=True)
source=json.loads((ROOT/'repro/baiqi_source/core_geometry.json').read_text(encoding='utf-8'))
width,height=1400,2200;assert glfw.init();glfw.window_hint(glfw.VISIBLE,glfw.FALSE);window=glfw.create_window(width,height,'BaiQi original component audit',None,None);assert window
glfw.make_context_current(window);live2d.init();live2d.glInit();texture=GL.glGenTextures(1);GL.glBindTexture(GL.GL_TEXTURE_2D,texture);GL.glTexImage2D(GL.GL_TEXTURE_2D,0,GL.GL_RGBA8,width,height,0,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE,None)
fbo=GL.glGenFramebuffers(1);GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,fbo);GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER,GL.GL_COLOR_ATTACHMENT0,GL.GL_TEXTURE_2D,texture,0)
model=live2d.Model();model.LoadModelJson(str(ROOT/'source/Delta/delta.model3.json'));model.Resize(width,height);model.SetAutoBlink(False);model.SetAutoBreath(False);model.SetScale(.94);model.StopAllMotions()
part_ids=model.GetPartIds();lookup={p['id']:p for p in source['parts']};params={p['id']:p for p in source['parameters']}
def reset(parameters=None,allowed=None):
    model.StopAllMotions();model.ResetExpressions();model.ResetAllParameters()
    values={p['id']:p['default'] for p in source['parameters']}
    for p in parameters or []:
        name=p['Id'];v=p['Value'];b=p.get('Blend','Add');values[name]=values[name]+v if b=='Add' else values[name]*v if b=='Multiply' else v
    for name,value in values.items():model.SetSaveParamById(name,max(params[name]['min'],min(params[name]['max'],value)))
    for index,name in enumerate(part_ids):model.SetPartOpacity(index,1. if allowed is None or name in allowed else 0.)
    model.Update(0.)
def render(path):
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,fbo);GL.glViewport(0,0,width,height);GL.glDisable(GL.GL_SCISSOR_TEST);live2d.clearBuffer(0,0,0,0);model.Draw();GL.glFinish()
    raw=GL.glReadPixels(0,0,width,height,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE);rgba=np.frombuffer(raw,dtype=np.uint8).reshape(height,width,4)[::-1].copy();alpha=rgba[:,:,3:4].astype(np.float32)
    rgba[:,:,:3]=np.minimum(255,rgba[:,:,:3].astype(np.float32)*255/np.maximum(alpha,1)).astype(np.uint8)
    path.parent.mkdir(parents=True,exist_ok=True);Image.fromarray(rgba).save(path)
    yy,xx=np.where(rgba[:,:,3]>4);return {'path':path.relative_to(out).as_posix(),'visible_pixels':len(xx),'bbox_pixels':[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)] if len(xx) else None}
reset();default=render(out/'default.png');mvp=list(model.GetMvp())
variants=[]
states=[{'id':v['id'],'parameters':v['parameters'],'source':v['source']} for v in source['variants']]
by_id={v['id']:v for v in states}
states.append({'id':'Machine_And_Screen','source_combination':['E-Machine-Open.exp3','E-Machine-Screen.exp3'],'parameters':by_id['E-Machine-Open.exp3']['parameters']+by_id['E-Machine-Screen.exp3']['parameters']})
for state in states:
    reset(state['parameters']);variants.append(dict(state,render=render(out/'variants'/(state['id']+'.png'))))
def descendants(name):
    result={name}
    for child in lookup[name]['children']:result.update(descendants(child))
    return result
sprites=[];default_visible={d['id'] for d in source['drawables'] if d['opacity']>.001}
for part in source['parts']:
    members=descendants(part['id']);wanted={d['id'] for d in source['drawables'] if d['part'] in members};chosen=None
    if not wanted.intersection(default_visible):chosen=next((v for v in source['variants'] if wanted.intersection(v['visible_drawables'])),None)
    allowed=set(members);node=part
    while node['parent']:
        allowed.add(node['parent']);node=lookup[node['parent']]
    # Clipping dependencies stay available in the SDK renderer. Their pixels
    # may be present, so these diagnostic sprites are not declared cutout art.
    required_masks={m for d in source['drawables'] if d['id'] in wanted for m in d['masks']}
    mask_parts={d['part'] for d in source['drawables'] if d['id'] in required_masks}
    for name in mask_parts:
        while name:
            allowed.add(name);name=lookup[name]['parent']
    reset(chosen['parameters'] if chosen else None,allowed)
    sprites.append({'id':part['id'],'source_name':part['source_name'],'variant':chosen['id'] if chosen else 'default','included_parts':sorted(allowed),
        'clipping_dependency_parts':sorted(mask_parts),'render':render(out/'parts'/(part['id']+'.png'))})
report={'character':'白绮','role':'original_2D_component_evidence_not_3D_output','default':default,'source_mvp':mvp,'variants':variants,'parts':sprites,
    'limits':'Part images can include ancestors or clipping dependencies. Hidden states remain in the exact UV/source geometry inventory.'}
(out/'source_render_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
model.DestroyRenderer();del model;live2d.glRelease();live2d.dispose();glfw.destroy_window(window);glfw.terminate();print('BAIQI_COMPONENT_SOURCE_RENDERS',len(sprites),len(variants))
