"""Extract four original eye poses and preserve every non-eye atlas pixel."""
import argparse
from pathlib import Path
import ctypes as c
import json
import sys

import numpy as np
from PIL import Image, ImageFilter

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'scripts'))
from baiqi_source_raster import SourceRaster

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--inputs', type=Path, required=True, help='Game export containing form_inputs.json.')
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()


class V2(c.Structure):
    _fields_ = [('x', c.c_float), ('y', c.c_float)]


core = c.CDLL(str(root / 'tools/cubism_core/Live2DCubismCore.dll'))


def call(name, result, types, *args):
    fn = getattr(core, 'csm' + name)
    fn.restype = result
    fn.argtypes = types
    return fn(*args)


vp, uint = c.c_void_p, c.c_uint
moc_bytes = (root / 'source/Delta/Delta.moc3').read_bytes()
storage = c.create_string_buffer(len(moc_bytes) + 63)
address = (c.addressof(storage) + 63) & ~63
c.memmove(address, moc_bytes, len(moc_bytes))
moc = call('ReviveMocInPlace', vp, (vp, uint), address, len(moc_bytes))
assert moc
size = call('GetSizeofModel', uint, (vp,), moc)
working = c.create_string_buffer(size + 15)
address = (c.addressof(working) + 15) & ~15
model = call('InitializeModelInPlace', vp, (vp, vp, uint), moc, address, size)
assert model


def array(name, dtype):
    return call('Get' + name, c.POINTER(dtype), (vp,), model)


source = SourceRaster(2800, 4400)
parts = {p['id']: p for p in source.source['parts']}


def descendants(name):
    return {name}.union(*(descendants(child) for child in parts[name]['children']))


face = descendants('Face') - {'Glasses'}
shadow = {row['id'] for row in source.drawables if row['part'] == 'Fhair' and 'Facecolor' in row['masks']}
parameters = {row['id']: i for i, row in enumerate(source.source['parameters'])}
param_ids = array('ParameterIds', c.c_char_p)
assert all(param_ids[idx].decode() == name for name, idx in parameters.items())
values, defaults = (array('Parameter' + name + 'Values', c.c_float) for name in ('', 'Default'))
xy = array('DrawableVertexPositions', c.POINTER(V2))
opacity = array('DrawableOpacities', c.c_float)
orders = array('RenderOrders', c.c_int)
crop = (960, 600, 1840, 1400)


def face_at(parameters_override):
    for i in parameters.values():
        values[i] = defaults[i]
    for key, value in parameters_override.items():
        values[parameters[key]] = value
    call('UpdateModel', None, (vp,), model)
    overrides = [dict(id=row['id'], positions_xy=[[v.x, v.y] for v in xy[i][:len(row['positions_xy'])]],
                      opacity=opacity[i], render_order=orders[i])
                 for i, row in enumerate(source.source['drawables'])]
    source.set_state({'draw_overrides': overrides})
    picture = source.render(face, include_drawables=shadow, exclude_drawables={'ArtMesh53'})
    eyes = source.render(descendants('Eyes'), exclude_drawables={'ArtMesh53'})
    mask = Image.fromarray(eyes).crop(crop).getchannel('A').filter(ImageFilter.GaussianBlur(.45))
    return np.array(Image.fromarray(picture).crop(crop)), mask


inputs = root / args.inputs
form = json.loads((inputs / 'form_inputs.json').read_text())['coat_off']
entry = form['materials']['BaiQi original face appearance']['images'][0]['path']
with Image.open(inputs / entry) as image:
    original = np.array(image.convert('RGBA'))
neutral, _ = face_at({})
assert original.shape == neutral.shape == (800, 880, 4)
states = {'half_blink': {'ParamEyeLOpen': .5, 'ParamEyeROpen': .5},
          'closed': {'ParamEyeLOpen': 0., 'ParamEyeROpen': 0.},
          'look_left': {'ParamEyeBallX': -.65}, 'look_right': {'ParamEyeBallX': .65}}
out = root / args.out
out.mkdir(parents=True, exist_ok=True)
Image.fromarray(original).save(out / 'neutral.png')
report = {}
for name, override in states.items():
    posed, mask = face_at(override)
    changed = np.max(np.abs(posed.astype(np.int16) - neutral), axis=-1) > 2
    assert changed.any()
    y, x = np.nonzero(changed)
    assert x.min() >= 280 and x.max() <= 600 and y.min() >= 375 and y.max() <= 465, name
    result = original.copy()
    result[changed] = posed[changed]
    Image.fromarray(result).save(out / (name + '.png'))
    mask.save(out / (name + '_mask.png'))
    report[name] = {'parameters': override, 'changed_pixels': int(changed.sum()),
                    'rect': [int(x.min()), int(y.min()), int(x.max()), int(y.max())]}
(out / 'probe.json').write_text(json.dumps(report, indent=2))
source.close()
print(report, flush=True)
