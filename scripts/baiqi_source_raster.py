"""Rasterize user ArtMeshes with original atlas UVs and clipping masks.

This is deterministic source-asset extraction, not a replacement for 3D
modeling. Mask dependencies are rendered separately and do not leak into
individual component images.
"""
import ctypes,json
from pathlib import Path
import glfw,numpy as np
from PIL import Image
from OpenGL import GL
from OpenGL.GL.shaders import compileProgram,compileShader
ROOT=Path(__file__).resolve().parents[1]
VERT='''#version 330
layout(location=0) in vec2 position; layout(location=1) in vec2 texcoord;
uniform mat4 mvp; out vec2 uv; out vec2 canvas;
void main(){gl_Position=mvp*vec4(position,0,1);uv=vec2(texcoord.x,1-texcoord.y);canvas=gl_Position.xy*.5+.5;}
'''
FRAG='''#version 330
in vec2 uv; in vec2 canvas; out vec4 result;
uniform sampler2D atlas; uniform sampler2D clipmap;
uniform vec4 multiplyColor; uniform vec4 screenColor;
uniform float opacity; uniform int maskPass; uniform int useMask; uniform int invertMask;
void main(){vec4 c=texture(atlas,uv);
if(maskPass==1){result=vec4(vec3(c.a),c.a);return;}
c.rgb*=multiplyColor.rgb;c.rgb=c.rgb+screenColor.rgb-c.rgb*screenColor.rgb;
c.rgb*=c.a;c*=opacity;
if(useMask==1){float m=texture(clipmap,canvas).a;if(invertMask==1)m=1-m;c*=m;}
result=c;}
'''
class SourceRaster:
    def __init__(self,width=1400,height=2200):
        self.width,self.height=width,height
        self.source=json.loads((ROOT/'repro/baiqi_source/core_geometry.json').read_text(encoding='utf-8'))
        manifest=ROOT/'artifacts/baiqi_component_audit/source_render_manifest.json'
        if not manifest.is_file():manifest=ROOT/'repro/baiqi_source/source_canvas.json'
        r=json.loads(manifest.read_text(encoding='utf-8'));self.mvp=np.array(r['source_mvp'],dtype=np.float32)
        assert glfw.init();glfw.window_hint(glfw.VISIBLE,glfw.FALSE);self.window=glfw.create_window(width,height,'BaiQi source ArtMesh raster',None,None);assert self.window;glfw.make_context_current(self.window)
        self.program=compileProgram(compileShader(VERT,GL.GL_VERTEX_SHADER),compileShader(FRAG,GL.GL_FRAGMENT_SHADER));GL.glUseProgram(self.program)
        self.uniform={n:GL.glGetUniformLocation(self.program,n) for n in ['mvp','atlas','clipmap','multiplyColor','screenColor','opacity','maskPass','useMask','invertMask']}
        GL.glUniformMatrix4fv(self.uniform['mvp'],1,False,self.mvp);GL.glUniform1i(self.uniform['atlas'],0);GL.glUniform1i(self.uniform['clipmap'],1)
        self.atlas=[]
        for texture in self.source['textures']:
            with Image.open(ROOT/texture['path']) as image:rgba=np.array(image.convert('RGBA'))
            tex=GL.glGenTextures(1);GL.glBindTexture(GL.GL_TEXTURE_2D,tex);GL.glTexImage2D(GL.GL_TEXTURE_2D,0,GL.GL_RGBA8,rgba.shape[1],rgba.shape[0],0,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE,rgba)
            GL.glTexParameteri(GL.GL_TEXTURE_2D,GL.GL_TEXTURE_MIN_FILTER,GL.GL_LINEAR);GL.glTexParameteri(GL.GL_TEXTURE_2D,GL.GL_TEXTURE_MAG_FILTER,GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D,GL.GL_TEXTURE_WRAP_S,GL.GL_CLAMP_TO_EDGE);GL.glTexParameteri(GL.GL_TEXTURE_2D,GL.GL_TEXTURE_WRAP_T,GL.GL_CLAMP_TO_EDGE);self.atlas.append(tex)
        self.vao=GL.glGenVertexArrays(1);GL.glBindVertexArray(self.vao);self.vbo=GL.glGenBuffers(1);self.ebo=GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER,self.vbo);GL.glEnableVertexAttribArray(0);GL.glVertexAttribPointer(0,2,GL.GL_FLOAT,False,16,ctypes.c_void_p(0));GL.glEnableVertexAttribArray(1);GL.glVertexAttribPointer(1,2,GL.GL_FLOAT,False,16,ctypes.c_void_p(8));GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER,self.ebo)
        self.output=self.framebuffer();self.mask_cache={};self.set_state()
        GL.glDisable(GL.GL_DEPTH_TEST);GL.glDisable(GL.GL_CULL_FACE);GL.glDisable(GL.GL_SCISSOR_TEST);GL.glEnable(GL.GL_BLEND)
    def framebuffer(self):
        tex=GL.glGenTextures(1);GL.glBindTexture(GL.GL_TEXTURE_2D,tex);GL.glTexImage2D(GL.GL_TEXTURE_2D,0,GL.GL_RGBA8,self.width,self.height,0,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE,None)
        for name in [GL.GL_TEXTURE_MIN_FILTER,GL.GL_TEXTURE_MAG_FILTER]:GL.glTexParameteri(GL.GL_TEXTURE_2D,name,GL.GL_LINEAR)
        for name in [GL.GL_TEXTURE_WRAP_S,GL.GL_TEXTURE_WRAP_T]:GL.glTexParameteri(GL.GL_TEXTURE_2D,name,GL.GL_CLAMP_TO_EDGE)
        fbo=GL.glGenFramebuffers(1);GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,fbo);GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER,GL.GL_COLOR_ATTACHMENT0,GL.GL_TEXTURE_2D,tex,0);assert GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)==GL.GL_FRAMEBUFFER_COMPLETE
        return fbo,tex
    def set_state(self,variant=None):
        for fbo,tex in self.mask_cache.values():GL.glDeleteFramebuffers(1,[fbo]);GL.glDeleteTextures([tex])
        self.mask_cache={};overrides={d['id']:d for d in (variant or {}).get('draw_overrides',[])}
        self.drawables=[dict(d,**{k:v for k,v in overrides.get(d['id'],{}).items() if k!='id'}) for d in self.source['drawables']];self.by_id={d['id']:d for d in self.drawables}
    def draw(self,d,mask_pass=False,erase=False):
        vertices=np.column_stack([d['positions_xy'],d['uvs']]).astype(np.float32);indices=np.array(d['indices'],dtype=np.uint16)
        GL.glBindVertexArray(self.vao);GL.glBindBuffer(GL.GL_ARRAY_BUFFER,self.vbo);GL.glBufferData(GL.GL_ARRAY_BUFFER,vertices.nbytes,vertices,GL.GL_STREAM_DRAW);GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER,self.ebo);GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER,indices.nbytes,indices,GL.GL_STREAM_DRAW)
        GL.glActiveTexture(GL.GL_TEXTURE0);GL.glBindTexture(GL.GL_TEXTURE_2D,self.atlas[d['texture']]);GL.glUniform1i(self.uniform['maskPass'],int(mask_pass));GL.glUniform1f(self.uniform['opacity'],d['opacity']);GL.glUniform4f(self.uniform['multiplyColor'],*d['multiply_color']);GL.glUniform4f(self.uniform['screenColor'],*d['screen_color'])
        GL.glUniform1i(self.uniform['useMask'],int(bool(d['masks']) and not mask_pass));GL.glUniform1i(self.uniform['invertMask'],int(bool(d['constant_flags']&8)))
        if mask_pass or d['blend_mode']==0:GL.glBlendFunc(GL.GL_ONE,GL.GL_ONE_MINUS_SRC_ALPHA)
        elif d['blend_mode']==1:GL.glBlendFuncSeparate(GL.GL_ONE,GL.GL_ONE,GL.GL_ZERO,GL.GL_ONE)
        else:GL.glBlendFuncSeparate(GL.GL_DST_COLOR,GL.GL_ONE_MINUS_SRC_ALPHA,GL.GL_ZERO,GL.GL_ONE)
        if erase:GL.glBlendFunc(GL.GL_ZERO,GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glDrawElements(GL.GL_TRIANGLES,len(indices),GL.GL_UNSIGNED_SHORT,None)
    def mask(self,ids):
        key=tuple(ids)
        if key not in self.mask_cache:
            target=self.framebuffer();GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,target[0]);GL.glViewport(0,0,self.width,self.height);GL.glClearColor(0,0,0,0);GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            GL.glActiveTexture(GL.GL_TEXTURE1);GL.glBindTexture(GL.GL_TEXTURE_2D,0)
            for name in ids:self.draw(self.by_id[name],True)
            self.mask_cache[key]=target
        return self.mask_cache[key][1]
    def render(self,parts=None,occluders=None,include_drawables=None,exclude_drawables=None):
        selected=lambda d:parts is None or d['part'] in parts or d['id'] in (include_drawables or set())
        chosen=[d for d in self.drawables if d['opacity']>.001 and d['id'] not in (exclude_drawables or set()) and (selected(d) or d['part'] in (occluders or set()))]
        for d in chosen:
            if d['masks']:self.mask(d['masks'])
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,self.output[0]);GL.glViewport(0,0,self.width,self.height);GL.glClearColor(0,0,0,0);GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        for d in sorted(chosen,key=lambda d:d['render_order']):
            GL.glActiveTexture(GL.GL_TEXTURE1);GL.glBindTexture(GL.GL_TEXTURE_2D,self.mask_cache[tuple(d['masks'])][1] if d['masks'] else 0);self.draw(d,erase=not selected(d))
        GL.glFinish();raw=GL.glReadPixels(0,0,self.width,self.height,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE);rgba=np.frombuffer(raw,dtype=np.uint8).reshape(self.height,self.width,4)[::-1].copy()
        alpha=rgba[:,:,3:4].astype(np.float32);rgba[:,:,:3]=np.minimum(255,rgba[:,:,:3].astype(np.float32)*255/np.maximum(alpha,1)).astype(np.uint8)
        return rgba
    def close(self):glfw.destroy_window(self.window);glfw.terminate()
if __name__=='__main__':
    r=SourceRaster();out=ROOT/'artifacts/baiqi_component_audit';rgba=r.render();Image.fromarray(rgba).save(out/'raw_default.png')
    original=np.array(Image.open(out/'default.png').convert('RGBA'));a=rgba[:,:,3]>4;b=original[:,:,3]>4
    report={'alpha_silhouette_iou':float((a&b).sum()/max(1,(a|b).sum())),'rgba_mean_abs_error':float(np.abs(rgba.astype(float)-original.astype(float)).mean()),'role':'source_renderer_validation'}
    (out/'raw_raster_validation.json').write_text(json.dumps(report,indent=2));print('BAIQI_RAW_SOURCE_RASTER',json.dumps(report));r.close()
