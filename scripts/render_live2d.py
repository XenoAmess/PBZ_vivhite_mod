"""Render the supplied Live2D using its runtime, with an invisible GL window."""
import json
import os
from pathlib import Path

os.environ['LIVE2D_PY_NO_BANNER'] = '1'
import glfw
import live2d
import numpy as np
from PIL import Image
from OpenGL import GL

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'live2d'
OUT.mkdir(parents=True, exist_ok=True)
assert glfw.init(), 'GLFW initialization failed'
glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
width, height = 1400, 2200
window = glfw.create_window(width, height, 'Delta offline render', None, None)
assert window, 'Unable to create hidden OpenGL context'
glfw.make_context_current(window)
live2d.init()
live2d.glInit()
texture = GL.glGenTextures(1)
GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, width, height, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)
framebuffer = GL.glGenFramebuffers(1)
GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, framebuffer)
GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, texture, 0)
assert GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) == GL.GL_FRAMEBUFFER_COMPLETE
model = live2d.Model()
model.LoadModelJson(str(ROOT / 'source/Delta/delta.model3.json'))
model.Resize(width, height)
model.SetAutoBlink(False)
model.SetAutoBreath(False)
model.Update(0.0)
model.SetScale(0.94)
GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, framebuffer)
GL.glViewport(0, 0, width, height)
GL.glDisable(GL.GL_SCISSOR_TEST)
live2d.clearBuffer(0, 0, 0, 0)
model.Draw()
GL.glFinish()
pixels = GL.glReadPixels(0, 0, width, height, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
rgba = np.frombuffer(pixels, dtype=np.uint8).reshape(height, width, 4)[::-1].copy()
# The SDK draws premultiplied alpha; PNG stores straight alpha.
alpha = rgba[:, :, 3:4].astype(np.float32)
rgba[:, :, :3] = np.minimum(255, rgba[:, :, :3].astype(np.float32) * 255 / np.maximum(alpha, 1)).astype(np.uint8)
Image.fromarray(rgba).save(OUT / 'Delta_front.png')
drawables = []
for i, name in enumerate(model.GetDrawableIds()):
    positions = model.GetDrawableVertices(i)
    drawables.append({'id': name, 'positions_xy': positions, 'indices': model.GetDrawableIndices(i)})
parameters = [{'id': name, 'value': model.GetParamValueByIndex(i),
               'min': model.GetParamMinByIndex(i), 'max': model.GetParamMaxByIndex(i)}
              for i, name in enumerate(model.GetParamIds())]
report = {'canvas_units': model.GetCanvasSize(), 'canvas_pixels': model.GetCanvasSizePixel(),
          'pixels_per_unit': model.GetPixelsPerUnit(), 'parts': model.GetPartIds(),
          'parameters': parameters, 'drawables': drawables,
          'warning': 'positions_xy are 2D ArtMeshes, not a reconstructed 3D body'}
(OUT / 'runtime_geometry.json').write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'drawables': len(drawables), 'parameters': len(parameters),
                  'canvas': report['canvas_pixels'], 'output': str(OUT)}, ensure_ascii=True))
model.DestroyRenderer()
del model
live2d.glRelease()
live2d.dispose()
glfw.destroy_window(window)
glfw.terminate()
