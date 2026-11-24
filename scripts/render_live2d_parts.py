"""Render original Cubism arm parts as a segmentation mask for rigging."""
import os
os.environ['LIVE2D_PY_NO_BANNER']='1'
from pathlib import Path
import argparse
import glfw
import live2d
import numpy as np
from OpenGL import GL
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--parts',default='Part31,Part35,Part38,Part39,Sleeve,Sleeve2,Bandage');parser.add_argument('--name',default='arms')
args=parser.parse_args();selected=set(args.parts.split(','))
assert glfw.init()
glfw.window_hint(glfw.VISIBLE,glfw.FALSE)
window=glfw.create_window(1400,2200,'Delta part mask',None,None)
glfw.make_context_current(window);live2d.init();live2d.glInit()
texture=GL.glGenTextures(1);GL.glBindTexture(GL.GL_TEXTURE_2D,texture)
GL.glTexImage2D(GL.GL_TEXTURE_2D,0,GL.GL_RGBA8,1400,2200,0,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE,None)
framebuffer=GL.glGenFramebuffers(1);GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,framebuffer)
GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER,GL.GL_COLOR_ATTACHMENT0,GL.GL_TEXTURE_2D,texture,0)
model=live2d.Model();model.LoadModelJson(str(ROOT/'source/Delta/delta.model3.json'))
model.Resize(1400,2200);model.SetAutoBlink(False);model.SetAutoBreath(False);model.Update(0.);model.SetScale(.94)
GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,framebuffer);GL.glViewport(0,0,1400,2200)
live2d.clearBuffer(0,0,0,0);model.Draw();GL.glFinish()
pixels=GL.glReadPixels(0,0,1400,2200,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE)
rgba=np.frombuffer(pixels,dtype=np.uint8).reshape(2200,1400,4)[::-1].copy()
for index,name in enumerate(model.GetPartIds()):
    if name in selected:
        model.SetPartOpacity(index,0.)
model.Update(0.)
live2d.clearBuffer(0,0,0,0);model.Draw();GL.glFinish()
pixels=GL.glReadPixels(0,0,1400,2200,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE)
hidden=np.frombuffer(pixels,dtype=np.uint8).reshape(2200,1400,4)[::-1].copy()
mask=np.where(np.max(np.abs(rgba.astype(np.int16)-hidden.astype(np.int16)),axis=2)>3,255,0).astype(np.uint8)
assert args.name.isidentifier()
path=ROOT/('artifacts/live2d/Delta_'+args.name+'_mask.png');Image.fromarray(mask).save(path)
print('CUBISM_PART_MASK',args.name,int((mask>127).sum()))
model.DestroyRenderer();del model;live2d.glRelease();live2d.dispose();glfw.destroy_window(window);glfw.terminate()
